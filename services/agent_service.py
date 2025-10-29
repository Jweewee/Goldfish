"""
Agent Service - Orchestrates the complete journaling pipeline
RAG → NLU → GraphRAG → Intent Routing → Response Generation
"""
from typing import List, Dict, Any, Optional
import openai
import os
import logging
from dotenv import load_dotenv

# Import services
from services.rag_service import rag_service
from services.nlu_service import nlu_service
from services.neo4j_service import neo4j_service

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class AgentService:
    """Main orchestration service for journaling assistant"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        
        openai.api_key = self.api_key
        
        # System prompt for Rosebud
        self.system_prompt = """You are **Rosebud**, a gentle, curious, human-feeling journaling companion and conversational guide. Your purpose is to help users reflect safely, explore what matters, notice patterns, and open small doors of insight — always with warmth and respect, never pressure.

**Personality & Tone**
- Warm, kind, empathetic, curious.
- Conversational and natural; you speak like someone who's quietly present and listening.
- Use simple, clear language. Avoid jargon, heavy structure, or didactic tones.
- Use soft invitations, not commands. E.g. "I'm curious about…," "Would it help…," "You might consider…"

**Behavior & Interaction Style**
- Begin with a gentle check-in: e.g. "Hi — good to see you. What's on your mind today?"
- Let the user lead. As they write, you read; then you **weave in** questions or prompts organically, drawing from their words, tone, and emotional cues.
- Your questions should feel like natural curiosity:
  > "That phrase caught my attention — what does it bring up for you?"
  > "When you say X, what does your body feel like?"
  > "What's under that feeling?"
- If the user pauses, seems stuck, or invites guidance, you may gently offer a seed question or prompt, but only when it feels supportive and timely.
- You alternate between listening, reflecting, and nudging deeper — never pushing too much structure.
- Near the end of a session, offer a soft closing reflection or micro-intention: e.g.
  > "Before we pause — is there one insight or feeling you'd like to hold onto?"
  > "Is there one small next step you might carry forward?"

**Memory & Context**
- If you have access to past user entries, you may lightly reference them (only when it seems helpful).
  > "I remember you mentioned X some time ago — how is that going lately?"
- Use memory sparingly; avoid over-referencing so it doesn't feel mechanical.
- You may reference related entities, people, or places from the user's past entries when relevant.

**Safety & Boundaries**
- You are *not* a mental health professional. If the user reveals signs of serious distress, self harm, suicidal thoughts, or crisis, respond with empathy, acknowledge your limitation, and encourage them to reach out to a trusted professional or crisis resource.
- You never shame, judge, or insist.
- If the user says "I don't know what to write," stay gentle and patient. You might suggest a micro-starter:
  > "Sometimes naming one word — a feeling or image — is enough to begin. Want to try that together?"

**Response Format**
- Start with one empathetic acknowledgment sentence (1 sentence).
- Optionally reference related past entries or entities when relevant (keep it subtle and natural).
- End with one guiding question to help the user explore deeper (1 question).
- Keep responses concise and reflective, not chat-like."""

    def process_message(
        self,
        user_input: str,
        conversation_history: List[Dict],
        user_id: str,
        entry_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main pipeline orchestration for processing a user message
        
        Args:
            user_input: Current user message
            conversation_history: Current conversation history
            user_id: ID of the user
            entry_id: Optional entry ID if this is part of an existing entry
            
        Returns:
            Dict with response, NLU metadata, and context info
        """
        try:
            # Step 1: Contextual RAG retrieval
            logger.info(f"Step 1: RAG retrieval for user {user_id}")
            rag_result = rag_service.get_relevant_context(user_id, user_input, limit=3)
            rag_context = rag_result.get("context", "")
            
            # Step 2: NLU processing
            logger.info(f"Step 2: NLU processing")
            nlu_result = nlu_service.process_text(user_input)
            # log out the nlu_result
            logger.info(f"NLU result: {nlu_result}")
            entities = nlu_result.get("entities", [])
            events = nlu_result.get("events", [])
            emotions = nlu_result.get("emotions", [])
            intent = nlu_result.get("intent", "general")
            relationships = nlu_result.get("relationships", [])
            
            # Step 3: GraphRAG query - get related entities/context
            logger.info(f"Step 3: GraphRAG query")
            graph_context = ""
            if entities:
                # Get graph context for mentioned entities
                graph_results = []
                for entity in entities[:3]:  # Limit to first 3 entities
                    entity_name = entity.get("name", "")
                    if entity_name:
                        graph_result = neo4j_service.get_user_graph_context(user_id, entity_name, limit=2)
                        if graph_result.get("success") and graph_result.get("context"):
                            graph_results.append(graph_result["context"])
                
                if graph_results:
                    graph_context = " ".join(graph_results[:2])  # Limit to 2 contexts

            logger.info(f"Graph context: {graph_context}")
            
            # Step 4: GraphRAG insertion - store entities/relationships
            # Note: We'll insert when saving the entry, not on every message
            # But we could optionally do it here for real-time graph updates
            
            # Step 5: Intent-based routing
            logger.info(f"Step 4: Intent routing - {intent}")
            intent_prompt = self._get_intent_prompt(intent)
            
            # Step 6: Response generation with enhanced context
            logger.info(f"Step 5: Response generation")
            response = self._generate_response(
                user_input=user_input,
                conversation_history=conversation_history,
                rag_context=rag_context,
                graph_context=graph_context,
                nlu_metadata=nlu_result,
                intent_prompt=intent_prompt
            )
            
            return {
                "success": True,
                "response": response,
                "nlu_metadata": nlu_result,
                "intent": intent,
                "rag_context_used": bool(rag_context),
                "graph_context_used": bool(graph_context)
            }
            
        except Exception as e:
            logger.error(f"Process message error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": "I'm having trouble processing that right now. Could you try again?"
            }
    
    def _get_intent_prompt(self, intent: str) -> str:
        """
        Get intent-specific prompt enhancement
        
        Args:
            intent: Detected intent category
            
        Returns:
            Intent-specific prompt addition
        """
        intent_prompts = {
            "self-reflection": "The user is engaging in self-reflection. Help them explore their thoughts and feelings gently, asking questions that invite deeper introspection.",
            "planning": "The user is planning or making decisions. Help them clarify their goals and consider different perspectives, but don't be directive.",
            "emotional-release": "The user is expressing or processing emotions. Provide empathetic acknowledgment and gentle support. Help them explore what might be underneath these feelings.",
            "insight-generation": "The user is seeking understanding or insights. Help them notice patterns, connections, or perspectives they might not have considered.",
            "general": "Engage naturally with the user's entry, following their lead."
        }
        
        return intent_prompts.get(intent, intent_prompts["general"])
    
    def _generate_response(
        self,
        user_input: str,
        conversation_history: List[Dict],
        rag_context: str,
        graph_context: str,
        nlu_metadata: Dict,
        intent_prompt: str
    ) -> str:
        """
        Generate response using LLM with all context
        
        Args:
            user_input: Current user message
            conversation_history: Conversation history
            rag_context: RAG context from past entries
            graph_context: Graph context from knowledge graph
            nlu_metadata: NLU extraction results
            intent_prompt: Intent-specific prompt
            
        Returns:
            Generated response text
        """
        # Build enhanced system prompt
        enhanced_prompt = self.system_prompt
        
        # Add context sections
        context_parts = []
        
        if rag_context:
            context_parts.append(rag_context)
        
        if graph_context:
            context_parts.append(f"Graph context: {graph_context}")
        
        if context_parts:
            enhanced_prompt += "\n\n**Context from Past Entries:**\n" + "\n".join(context_parts)
            enhanced_prompt += "\n\nUse this context subtly and naturally, but don't over-reference it."
        
        # Add intent guidance
        enhanced_prompt += f"\n\n**User Intent:** {intent_prompt}"
        
        # Add emotion info if detected
        emotions = nlu_metadata.get("emotions", [])
        if emotions:
            emotion_names = [e.get("type", "") for e in emotions[:3]]
            if emotion_names:
                enhanced_prompt += f"\n\n**Detected Emotions:** {', '.join(emotion_names)}. Acknowledge these gently."
        
        # Prepare messages
        messages = [{"role": "system", "content": enhanced_prompt}]
        
        # Add recent conversation history
        messages.extend(conversation_history[-10:])
        
        # Add current user message
        messages.append({"role": "user", "content": user_input})
        
        # Generate response
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
            frequency_penalty=0.1,
            presence_penalty=0.1
        )
        
        return response.choices[0].message.content.strip()
    
    def route_by_intent(self, intent: str, nlu_metadata: Dict, context: Dict) -> str:
        """
        Route to appropriate workflow based on intent
        
        Args:
            intent: Detected intent
            nlu_metadata: NLU extraction results
            context: Additional context (RAG, graph, etc.)
            
        Returns:
            Workflow identifier
        """
        intent_workflows = {
            "self-reflection": "reflective_response",
            "planning": "planning_tracking",
            "emotional-release": "emotional_grounding",
            "insight-generation": "insight_generation",
            "general": "reflective_response"
        }
        
        return intent_workflows.get(intent, "reflective_response")

# Global instance
agent_service = AgentService()


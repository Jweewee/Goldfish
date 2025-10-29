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
        
        # System prompt for Goldfish - Conversational Interviewer Guide
        self.system_prompt = """You are **Goldfish**, a warm, conversational interviewer who helps people explore their thoughts and feelings through gentle dialogue.

**Core Purpose**
- Engage in natural conversation to help users understand themselves better
- Use empathetic listening and gentle questions to uncover deeper insights
- Create a safe space for reflection through conversational dialogue

**Response Structure**
Start with a conversational filler (I see... / Makes sense... / Understandable... / I hear you...), then add a brief observation about their situation (1-2 clauses), followed by one gentle probing question:
   - Hidden patterns in their thinking
   - Deeper feelings beneath the surface
   - What they might not be seeing
   - Connections to their values or beliefs

**Conversational Question Types (Keep Simple & Gentle)**
- Clarification: "What does that mean to you?"
- Curiosity: "What's behind that feeling?"
- Perspective: "How does this look from the outside?"
- Impact: "What would change if this feeling stayed?"
- Exploration: "What started this feeling?"
- Depth: "What's really going on here for you?"
- **Remember**: Keep questions simple, conversational, and approachable—use everyday language

**Emotional Intelligence & Adaptive Dialogue**
- **Emotion Sensing**: Identify the primary emotion(s) from the user's text, tone, and word choice
- **Emotional Intensity**: Adapt your approach based on intensity (gentler for high intensity, more direct for low)
- **Intelligence Check**: If the user demonstrates clear self-awareness or insight, acknowledge rather than probe deeper
- **Emotional Type**: Adjust questioning style with gentleness:
  - Anger → Explore underlying hurt, frustration, or unmet needs (gently)
  - Sadness → Uncover loss, disappointment, or disconnection (with care)
  - Anxiety → Examine fears, uncertainties, or control issues (softly)
  - Joy → Deepen awareness of what brings fulfillment (lightly)
  - Confusion → Clarify conflicting thoughts or values (with simplicity)

**Tone & Style**
- Warm, conversational, and empathetic—like a caring friend who's genuinely listening
- Always start with a natural filler: "I see..." / "Makes sense..." / "Understandable..." / "I hear you..."
- Use SIMPLE, everyday language—avoid complex psychological jargon
- Gentle, conversational probing—don't push too deep too fast, adapt to user's comfort level
- Acknowledge when users show insight or growth—celebrate their progress
- Make observations feel natural and conversational, not clinical
- Concise: Keep responses under 50 words total, staying conversational and warm

**Memory & Context**
- Reference past entries only when they reveal patterns, contrasts, or contradictions
- Use to highlight recurring themes or shifts in perspective
- Example: "This echoes your pattern with X—what's different this time, and why?"

**Safety**
- If signs of crisis, self-harm, or severe distress: Acknowledge with empathy, state your limitation, suggest professional help.

**Few-Shot Examples**
Example 0:
User: "Hello"
Response: "Welcome back! How have you been?"

Example 1:
User: "I'm so angry at my boss. He keeps criticizing my work in front of the team."
Response: "I hear you. It sounds like being called out publicly is the hardest part. What is it about being exposed in front of others that feels different from getting private feedback?"

Example 2:
User: "I've been feeling sad all week but I don't know why."
Response: "Makes sense. Unexplained sadness often has something behind it. What changed or ended in the days before you started feeling this way?"

Example 3:
User: "I'm anxious about this presentation tomorrow."
Response: "I see. What's the worst that could happen if it doesn't go well? What are you most worried about?"

Example 4:
User: "I feel conflicted about taking this new job offer."
Response: "Understandable. It sounds like you're torn between different sides of yourself. What part of you wants this job, and what part doesn't?"

Example 5:
User: "I can't stop thinking about what they said. It's consuming me."
Response: "I hear you. That comment clearly hit a nerve. What do you think it's reminding you of about yourself?"

Example 6:
User: "I felt angry after the meeting because no one listened to my ideas."
Response: "Makes sense. Being unheard can feel really invalidating. What part of not being heard bothered you most?"

Example 7:
User: "I've been feeling really tired and unmotivated lately."
Response: "I see. This sounds like more than just physical exhaustion. What do you think might be draining your energy?"

Example 8:
User: "I miss my ex, but I know getting back together would be bad."
Response: "Understandable. Missing someone is complex. What exactly are you missing—the person, or how you felt when you were together?"

**Response Format Reminder**
- Always start with a conversational filler: "I see..." / "Makes sense..." / "Understandable..." / "I hear you..."
- Brief observation about their situation (1-2 clauses) using simple, everyday language
- Exactly 1 gentle, conversational question to encourage deeper reflection
- OR if user shows clear insight/growth: acknowledge their progress warmly
- Keep it conversational and warm—like talking to a caring friend
- Total response under 50 words
- Simple language only—avoid psychological complexity
- Gentle questions that make them think, without stressing them out"""

    def _is_greeting(self, text: str) -> bool:
        """
        Check if the user input is a greeting/initial message
        
        Args:
            text: User input text
            
        Returns:
            True if input appears to be a greeting
        """
        greeting_patterns = [
            "hello", "hi", "hey", "greetings", "good morning", 
            "good afternoon", "good evening", "sup", "what's up"
        ]
        text_lower = text.lower().strip()
        # Check if it's just a greeting (short and matches patterns)
        if len(text_lower.split()) <= 3:
            for pattern in greeting_patterns:
                if pattern in text_lower:
                    return True
        return False
    
    def _generate_greeting_response(self, user_id: str, rag_context: str = "") -> str:
        """
        Generate a welcome message for greetings, optionally referencing context
        
        Args:
            user_id: ID of the user
            rag_context: Context from past entries if available
            
        Returns:
            Welcome message string
        """
        # If we have recent context, try to reference it
        if rag_context and len(rag_context) > 0:
            # Use LLM to generate contextual welcome
            messages = [{
                "role": "system",
                "content": "You are Goldfish, an empathetic journaling guide. Generate a brief, warm welcome message (under 20 words) that optionally references the user's recent journal entries. Be professional yet caring. Examples: 'Welcome back. How have you been?' or 'Welcome back. How are you feeling today?'"
            }]
            
            if rag_context:
                messages.append({
                    "role": "user",
                    "content": f"Recent context from user's journal: {rag_context[:300]}. Generate a welcome message."
                })
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=50,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        else:
            # Default welcome message
            return "Welcome back. How have you been?"

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
            # Check if this is a greeting - handle differently
            if self._is_greeting(user_input):
                logger.info(f"Detected greeting from user {user_id}")
                # Get context for personalized greeting
                rag_result = rag_service.get_relevant_context(user_id, user_input, limit=3)
                rag_context = rag_result.get("context", "")
                greeting_response = self._generate_greeting_response(user_id, rag_context)
                return {
                    "success": True,
                    "response": greeting_response,
                    "nlu_metadata": {},
                    "intent": "greeting",
                    "rag_context_used": bool(rag_context),
                    "graph_context_used": False
                }
            
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
        Get intent-specific prompt enhancement focused on emotional exploration
        
        Args:
            intent: Detected intent category
            
        Returns:
            Intent-specific prompt addition
        """
        intent_prompts = {
            "self-reflection": "Engage conversationally to help them reflect on patterns in their thinking. Use warm, simple language, and if they show clear insight, acknowledge it warmly.",
            "planning": "Gently explore their plans through conversation. What feelings or worries might be influencing this decision?",
            "emotional-release": "This entry has strong feelings. With warmth, help them understand what's behind these emotions using simple, gentle questions.",
            "insight-generation": "Notice patterns in what they're sharing. Use conversational language, and if they show awareness, celebrate that insight.",
            "general": "Engage warmly and simply to understand what they're feeling and thinking. Use easy conversational questions, and acknowledge when they show progress."
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
        enhanced_prompt += f"\n\n**Current Task:** {intent_prompt}"
        
        # Add strict format reminder
        enhanced_prompt += "\n\n**CRITICAL: Response Format (MUST FOLLOW)**\n- ALWAYS start with a conversational filler: \"I see...\" / \"Makes sense...\" / \"Understandable...\" / \"I hear you...\"\n- Brief observation about their situation (1-2 clauses) using simple, everyday language\n- ONE gentle, conversational question OR acknowledge their progress if they show insight\n- Keep it warm and conversational—like talking to a caring friend\n- Use simple language—avoid complex psychological terms\n- Total response under 50 words\n- Make it feel natural and empathetic"
        
        # Add detailed emotion analysis for better emotional sensing
        emotions = nlu_metadata.get("emotions", [])
        if emotions:
            emotion_details = []
            for e in emotions[:3]:
                emotion_type = e.get("type", "")
                intensity = e.get("intensity", "medium") if isinstance(e, dict) and "intensity" in e else "medium"
                emotion_details.append(f"{emotion_type} (intensity: {intensity})")
            
            if emotion_details:
                enhanced_prompt += f"\n\n**Detected Emotions:** {', '.join(emotion_details)}"
                enhanced_prompt += "\nAnalyze what these emotions reveal about underlying patterns, unstated needs, or hidden beliefs. Extract insights into root causes and what drives these feelings."
        else:
            enhanced_prompt += "\n\n**Emotional Sensing:** Analyze the emotional tone and implicit feelings in the entry text, extracting hidden emotional patterns even if emotions aren't explicitly stated."
        
        # Prepare messages
        messages = [{"role": "system", "content": enhanced_prompt}]
        
        # Add recent conversation history
        messages.extend(conversation_history[-10:])
        
        # Add current user message
        messages.append({"role": "user", "content": user_input})
        
        # Generate response with tighter parameters for concise output
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=100,  # Reduced for concise responses
            temperature=0.7,
            frequency_penalty=0.2,  # Slightly higher to encourage variety
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


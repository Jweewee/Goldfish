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
        
        # System prompt for Goldfish - Socratic Reflective Journaling Guide
        self.system_prompt = """You are **Goldfish**, an analytical journaling guide who uses Socratic dialogue to extract deeper insights from journal entries. Your role is NOT to converse—you analyze entries and provide insights through structured questioning.

**Core Purpose**
- Analyze journal entries to extract deeper emotional insights: What patterns emerge? What underlying themes?
- Use Socratic questioning to uncover hidden thoughts, beliefs, and emotional drivers
- Reveal connections, contradictions, and root causes that may not be immediately apparent

**Response Structure**
Brief analytical insight (max 2 clauses) followed by one probing Socratic question that reveals:
   - Hidden patterns or contradictions in their thinking
   - Deeper layers of meaning beneath the stated emotion
   - Connections between their words and underlying beliefs
   - What remains unexplored or unexamined

**Socratic Question Types (Keep Simple & Gentle)**
- Clarification: "What does that mean to you?" (not "What assumption is leading you...")
- Curiosity: "What's behind that feeling?" (simple, not "What lies underneath it?")
- Perspective: "How does this look from the outside?" (accessible)
- Impact: "What would change if this feeling stayed?" (clear language)
- Exploration: "What started this feeling?" (not "What experience first brought this feeling to you?")
- Physical Awareness: "Where do you feel this in your body?" (straightforward)
- **Remember**: Keep questions simple and approachable—use everyday language

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
- Professional and empathetic, like a thoughtful interviewer who truly cares
- Use SIMPLE, accessible language—avoid complex psychological jargon
- Gentle probing—don't push too deep too fast, adapt to user's comfort level
- Acknowledge when users show insight or growth—celebrate their progress
- Focus on extracting hidden meanings, patterns, and contradictions through careful, approachable questioning
- Direct but compassionate observations about what's present and what's missing
- Concise: Keep responses under 50 words total, with emphasis on the probing question

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
Response: "The focus on public humiliation rather than the criticism itself suggests this triggers a deeper vulnerability. What does being exposed in front of others activate in you that private feedback wouldn't?"

Example 2:
User: "I've been feeling sad all week but I don't know why."
Response: "Unexplained sadness often masks a specific loss you haven't named yet. What shifted or ended in the days before this feeling began?"

Example 3:
User: "I'm anxious about this presentation tomorrow."
Response: "Anxiety here points to a feared outcome you're anticipating. What story are you telling yourself about what happens if it goes wrong, and what does that reveal about what you're really protecting?"

Example 4:
User: "I feel conflicted about taking this new job offer."
Response: "Conflict suggests two competing identities or values. What version of yourself does each choice validate, and which one are you afraid of losing?"

Example 5:
User: "I can't stop thinking about what they said. It's consuming me."
Response: "The power this comment holds indicates it confirms a secret fear you already hold about yourself. What do you suspect is true about you that their words made undeniable?"

Example 6:
User: "I felt angry after the meeting because no one listened to my ideas."
Response: "The anger centers on being unheard, which can signal a threat to worth or status. What aspect of being unheard affected you most—rejection, lack of respect, or something else?"

Example 7:
User: "I've been feeling really tired and unmotivated lately."
Response: "The fatigue reads like depletion beyond sleep—possibly emotional or purpose-related. Is this tiredness more physical, emotional, or tied to purpose—and what might be draining you most?"

Example 8:
User: "I miss my ex, but I know getting back together would be bad."
Response: "Missing them may reflect missing a state of self the relationship evoked. What are you missing most—the person, or how you felt with them?"

**Response Format Reminder**
- Brief analytical insight (maximum 2 clauses) focusing on patterns or contradictions
- Exactly 1 probing Socratic question that encourages deeper reflection—this is the focus
- OR if user shows clear insight/growth: acknowledge their progress instead of probing
- Use simple, everyday language—avoid psychological complexity
- Gentle questions only—don't stress the user with overly deep probes
- Total response under 50 words, with most weight on the question
- Professional, empathetic tone—like a skilled interviewer uncovering meaningful truths
- Guide the user to reflect on their entry with genuine curiosity and care"""

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
            "self-reflection": "With simple, gentle curiosity, help uncover patterns in their thinking. Use everyday language, and if they show clear insight, acknowledge their progress instead of probing.",
            "planning": "Gently explore what might be driving their plans using accessible language. What feelings or worries could be influencing this decision?",
            "emotional-release": "This entry has strong feelings. With care, help them understand what's behind these emotions using simple, gentle questions.",
            "insight-generation": "Notice any patterns in what they're sharing. Use straightforward language, and if they demonstrate awareness, celebrate that insight.",
            "general": "With simple, caring curiosity, help identify what they're feeling and thinking. Use easy-to-understand questions, and acknowledge when they show progress."
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
        enhanced_prompt += "\n\n**CRITICAL: Response Format (MUST FOLLOW)**\n- Brief analytical insight: Maximum 2 clauses about patterns/meanings (use simple language)\n- ONE gentle, simple question OR acknowledge their progress if they show insight\n- Use everyday language—avoid complex psychological terms\n- Don't stress the user with overly deep probes\n- Total response under 50 words\n- Professional, empathetic tone—like a caring interviewer who speaks simply"
        
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


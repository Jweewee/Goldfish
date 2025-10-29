"""
NLU Service - Entity, Event, Emotion extraction and Intent classification
Uses LLM for structured entity extraction with semantic and emotional nuance prioritization
"""
import os
import openai
from typing import List, Dict, Any, Optional
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Try to import spaCy, but handle gracefully if not installed
try:
    import spacy
    SPACY_AVAILABLE = True
    try:
        # Try to load the model
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.warning("spaCy model 'en_core_web_sm' not found. Please run: python -m spacy download en_core_web_sm")
        nlp = None
        SPACY_AVAILABLE = False
except ImportError:
    logger.warning("spaCy not installed. Entity extraction will be disabled.")
    SPACY_AVAILABLE = False
    nlp = None

class NLUService:
    """Service for Natural Language Understanding"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        
        openai.api_key = self.api_key
        
        self.nlp = nlp  # Will be None if spaCy not available or model not loaded
    
    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks
        
        Args:
            response_text: Raw response text that may contain markdown code blocks
            
        Returns:
            Clean JSON string ready for parsing
        """
        import json
        import re
        
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        # Pattern: ```json ... ``` or ``` ... ```
        # Handle multiline JSON with proper matching
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            json_str = json_match.group(1).strip()
            # Try to parse to validate it's valid JSON
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass  # Not valid JSON, continue to other methods
        
        # If no code block or code block didn't contain valid JSON,
        # try to find JSON object/array in the text
        # PRIORITIZE objects over arrays (we want a dict, not a list)
        # Use a more robust approach: find balanced brackets/braces
        def find_json_start_end(text, start_char='{', end_char='}'):
            """Find balanced JSON object/array boundaries"""
            start_idx = text.find(start_char)
            if start_idx == -1:
                return None, None
            
            depth = 0
            in_string = False
            escape = False
            
            for i in range(start_idx, len(text)):
                char = text[i]
                
                if escape:
                    escape = False
                    continue
                
                if char == '\\':
                    escape = True
                    continue
                
                if char == '"':
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            return start_idx, i + 1
            
            return None, None
        
        # Try to find JSON OBJECT first (we want a dict, not a list)
        start, end = find_json_start_end(text, '{', '}')
        if start is not None and end is not None:
            json_str = text[start:end].strip()
            try:
                parsed = json.loads(json_str)
                # Verify it's actually an object/dict
                if isinstance(parsed, dict):
                    return json_str
            except json.JSONDecodeError:
                pass
        
        # Fallback: Try to find JSON array (but we'll handle this in the calling code)
        start, end = find_json_start_end(text, '[', ']')
        if start is not None and end is not None:
            json_str = text[start:end].strip()
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass
        
        # Fallback: return original text (will fail gracefully)
        return text
    
    def extract_graph_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract graph entities using LLM with structured JSON output
        Prioritizes precision and semantic nuance for journaling contexts
        
        Args:
            text: Text to extract entities from
            
        Returns:
            Dict with people, organizations, events, topics, emotions (with valence/intensity), relationships
        """
        try:
            prompt = f"""You are an expert in reflective journaling entity extraction.
Extract structured data from this text, categorizing into:
- people: Names of people mentioned
- organizations: Companies, institutions, groups
- events: Specific events or activities
- places: Locations, places, geographical entities
- dates: Specific dates, times, or temporal references
- topics: Themes or subjects discussed
- emotions: Each with "type" (emotion name), "valence" (positive/negative/neutral), and "intensity" (1-5 scale)
- relationships: IMPORTANT - Extract relationships between entities mentioned in the text. Look for any connections, associations, or interactions between entities. Examples:
  - Person to Organization: "works at", "studies at", "visits"
  - Person to Person: "knows", "lives with", "met"
  - Person to Place: "lives in", "visited", "from"
  - Person to Event: "attended", "organized", "participated in"
  - Organization to Place: "located in", "has office in"
  - Any other meaningful connections between entities
  
  Each relationship should have:
  - from: source entity name (exact match from entities list)
  - to: target entity name (exact match from entities list)
  - type: concise relation verb phrase describing the connection (e.g., "works at", "promised by", "related to")
  - from_type: one of [person, organization, event, place, date, user]
  - to_type: one of [person, organization, event, place, date, user]
  - confidence: number 0.0-1.0 (how confident you are this relationship exists)

IMPORTANT: If there are multiple entities mentioned, look for relationships between them. Even indirect relationships count (e.g., "I went to McDonald's" creates a relationship between "I" and "McDonald's").

Return a JSON OBJECT (not an array) with this exact structure:
{{
  "people": ["name1", "name2"],
  "organizations": ["org1"],
  "events": ["event1"],
  "places": ["place1"],
  "dates": ["date1"],
  "topics": ["topic1"],
  "emotions": [{{"type": "anxiety", "valence": "negative", "intensity": 4}}],
  "relationships": [{{"from": "Chloe", "to": "Apple", "type": "works at", "from_type": "person", "to_type": "organization", "confidence": 0.92}}]
}}

Text: {text[:2000]}

Return ONLY the JSON object, no markdown, no code blocks, no other text:"""
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert in reflective journaling entity extraction. Return ONLY a valid JSON object (not an array). Do not use markdown code blocks. Return the raw JSON object starting with { and ending with }."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000,
                response_format={"type": "json_object"}  # Force JSON object output
            )
            
            import json
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from markdown code blocks if present
            json_str = self._extract_json_from_response(response_text)
            
            try:
                data = json.loads(json_str)
                
                # Handle case where LLM returns a list instead of an object
                if isinstance(data, list):
                    logger.warning("LLM returned a list instead of an object. Using first element if available.")
                    if len(data) > 0 and isinstance(data[0], dict):
                        data = data[0]
                    else:
                        # If it's an empty list or not a dict, return empty structure
                        return {
                            "people": [],
                            "organizations": [],
                            "events": [],
                            "places": [],
                            "dates": [],
                            "topics": [],
                            "emotions": [],
                            "relationships": []
                        }
                
                # Ensure data is a dictionary before accessing keys
                if not isinstance(data, dict):
                    logger.warning(f"Expected dict but got {type(data)}. Returning empty structure.")
                    return {
                        "people": [],
                        "organizations": [],
                        "events": [],
                        "places": [],
                        "dates": [],
                        "topics": [],
                        "emotions": [],
                        "relationships": []
                    }
                
                # Ensure all expected keys exist
                return {
                    "people": data.get("people", []),
                    "organizations": data.get("organizations", []),
                    "events": data.get("events", []),
                    "places": data.get("places", []),
                    "dates": data.get("dates", []),
                    "topics": data.get("topics", []),
                    "emotions": data.get("emotions", []),
                    "relationships": data.get("relationships", [])
                }
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse graph entities JSON: {json_str[:200]}")
                logger.error(f"JSON decode error: {str(e)}")
                return {
                    "people": [],
                    "organizations": [],
                    "events": [],
                    "places": [],
                    "dates": [],
                    "topics": [],
                    "emotions": [],
                    "relationships": []
                }
                
        except Exception as e:
            logger.error(f"Extract graph entities error: {str(e)}")
            return {
                "people": [],
                "organizations": [],
                "events": [],
                "places": [],
                "dates": [],
                "topics": [],
                "emotions": [],
                "relationships": []
            }
    
    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract entities using LLM (fallback to spaCy if available)
        
        Args:
            text: Text to extract entities from
            
        Returns:
            List of entities with type, name, and properties
        """
        # Use LLM-based extraction for better semantic understanding
        try:
            graph_data = self.extract_graph_entities(text)
            entities = []
            
            # Convert graph entities to the old format for backward compatibility
            for person in graph_data.get("people", []):
                entities.append({
                    "type": "PERSON",
                    "name": person,
                    "start": -1,  # Position not available from LLM
                    "end": -1
                })
            
            for org in graph_data.get("organizations", []):
                entities.append({
                    "type": "ORG",
                    "name": org,
                    "start": -1,
                    "end": -1
                })
            
            for event in graph_data.get("events", []):
                entities.append({
                    "type": "EVENT",
                    "name": event,
                    "start": -1,
                    "end": -1
                })
            
            # Include topics as entities
            for place in graph_data.get("places", []):
                entities.append({
                    "type": "PLACE",
                    "name": place,
                    "start": -1,
                    "end": -1
                })
            
            for date in graph_data.get("dates", []):
                entities.append({
                    "type": "DATE",
                    "name": date,
                    "start": -1,
                    "end": -1
                })
            
            for topic in graph_data.get("topics", []):
                entities.append({
                    "type": "TOPIC",
                    "name": topic,
                    "start": -1,
                    "end": -1
                })
            
            return entities
            
        except Exception as e:
            logger.error(f"Extract entities error: {str(e)}")
            # Fallback to spaCy if available
            if self.nlp:
                try:
                    doc = self.nlp(text)
                    entities = []
                    for ent in doc.ents:
                        entities.append({
                            "type": ent.label_,
                            "name": ent.text.strip(),
                            "start": ent.start_char,
                            "end": ent.end_char
                        })
                    return entities
                except Exception as e2:
                    logger.error(f"spaCy fallback error: {str(e2)}")
            return []
    
    def extract_emotions(self, text: str) -> List[Dict]:
        """
        Extract emotions from text using LLM with valence and intensity
        
        Args:
            text: Text to extract emotions from
            
        Returns:
            List of emotions with type, valence, and intensity (1-5)
        """
        try:
            # Use graph extraction which includes emotions with valence/intensity
            graph_data = self.extract_graph_entities(text)
            emotions = graph_data.get("emotions", [])
            
            # Convert to backward-compatible format if needed
            formatted_emotions = []
            for emotion in emotions:
                if isinstance(emotion, dict):
                    formatted_emotions.append({
                        "type": emotion.get("type", ""),
                        "valence": emotion.get("valence", "neutral"),
                        "intensity": emotion.get("intensity", 3),
                        "value": f"{emotion.get('valence', 'neutral')} intensity {emotion.get('intensity', 3)}/5"  # Backward compat
                    })
                else:
                    # Fallback for old format
                    formatted_emotions.append(emotion)
            
            return formatted_emotions
            
        except Exception as e:
            logger.error(f"Extract emotions error: {str(e)}")
            return []
    
    def extract_events(self, text: str) -> List[Dict]:
        """
        Extract events from text using LLM
        
        Args:
            text: Text to extract events from
            
        Returns:
            List of events with name and description
        """
        try:
            prompt = f"""Analyze the following journal entry and extract significant events or activities mentioned.
Return a JSON array of events, each with "name" (brief event name) and "description" (optional brief description).

Text: {text[:1000]}

Return ONLY a JSON array, no other text. Example format:
[{{"name": "Job interview", "description": "Interviewed for software engineer position"}}, {{"name": "Birthday dinner", "description": ""}}]

Events:"""
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts events from text. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            import json
            events_json = response.choices[0].message.content.strip()
            
            # Extract JSON from markdown code blocks if present
            events_json = self._extract_json_from_response(events_json)
            
            try:
                events = json.loads(events_json)
                if isinstance(events, list):
                    return events
                else:
                    return []
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse events JSON: {events_json[:200]}")
                return []
                
        except Exception as e:
            logger.error(f"Extract events error: {str(e)}")
            return []
    
    def infer_relationships(self, entities: List[Dict], text: str) -> List[Dict]:
        """
        Infer relationships between entities using LLM
        
        Args:
            entities: List of extracted entities
            text: Original text for context
            Returns:
            List of relationships with source, target, and type
        """
        if len(entities) < 2:
            return []
        
        try:
            # Prepare entity list for prompt
            entity_names = [e["name"] for e in entities[:10]]  # Limit to 10 entities
            
            prompt = f"""Given the following entities and the text context, identify meaningful relationships between them.
Return a JSON array of relationships, each with "source" (entity name), "target" (entity name), 
and "type" (relationship type like "works_at", "lives_in", "related_to", "met_at", etc.).

Entities: {', '.join(entity_names)}
Text context: {text[:800]}

Return ONLY a JSON array, no other text. Example format:
[{{"source": "John", "target": "Google", "type": "works_at"}}, {{"source": "Sarah", "target": "New York", "type": "lives_in"}}]

Relationships:"""
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that infers relationships between entities. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            import json
            rels_json = response.choices[0].message.content.strip()
            
            # Extract JSON from markdown code blocks if present
            rels_json = self._extract_json_from_response(rels_json)
            
            try:
                relationships = json.loads(rels_json)
                if isinstance(relationships, list):
                    return relationships
                else:
                    return []
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse relationships JSON: {rels_json[:200]}")
                return []
                
        except Exception as e:
            logger.error(f"Infer relationships error: {str(e)}")
            return []
    
    def classify_intent(self, text: str) -> str:
        """
        Classify the intent behind the journal entry
        
        Args:
            text: Text to classify
            
        Returns:
            Intent category: "self-reflection", "planning", "emotional-release", "insight-generation", or "general"
        """
        try:
            prompt = f"""Classify the intent or purpose of this journal entry into one of these categories:
- "self-reflection": User is reflecting on themselves, their thoughts, feelings, or experiences
- "planning": User is planning goals, events, or making decisions
- "emotional-release": User is expressing or processing emotions
- "insight-generation": User is seeking understanding or insights about a situation
- "general": General journaling without a specific clear intent

Text: {text[:1000]}

Return ONLY the category name, nothing else. Category:"""
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that classifies journal entry intents. Return only the category name."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=20,
                temperature=0.2
            )
            
            intent = response.choices[0].message.content.strip().lower()
            
            # Validate intent
            valid_intents = ["self-reflection", "planning", "emotional-release", "insight-generation", "general"]
            if intent in valid_intents:
                return intent
            else:
                # Try to match partial
                for valid_intent in valid_intents:
                    if valid_intent in intent:
                        return valid_intent
                return "general"
                
        except Exception as e:
            logger.error(f"Classify intent error: {str(e)}")
            return "general"
    
    def process_text(self, text: str) -> Dict[str, Any]:
        """
        Complete NLU processing pipeline
        
        Args:
            text: Text to process
            
        Returns:
            Dict with entities, events, emotions, intent, and relationships
        """
        # Use LLM-based graph extraction ONCE for comprehensive extraction
        graph_data = self.extract_graph_entities(text)
        
        # Extract entities from graph_data (no additional LLM call)
        entities = []
        for person in graph_data.get("people", []):
            entities.append({
                "type": "PERSON",
                "name": person,
                "start": -1,
                "end": -1
            })
        for org in graph_data.get("organizations", []):
            entities.append({
                "type": "ORG",
                "name": org,
                "start": -1,
                "end": -1
            })
        for event in graph_data.get("events", []):
            entities.append({
                "type": "EVENT",
                "name": event,
                "start": -1,
                "end": -1
            })
        for topic in graph_data.get("topics", []):
            entities.append({
                "type": "TOPIC",
                "name": topic,
                "start": -1,
                "end": -1
            })
        
        for place in graph_data.get("places", []):
            entities.append({
                "type": "PLACE",
                "name": place,
                "start": -1,
                "end": -1
            })
        
        for date in graph_data.get("dates", []):
            entities.append({
                "type": "DATE",
                "name": date,
                "start": -1,
                "end": -1
            })
        
        # Extract emotions from graph_data (no additional LLM call)
        emotions = []
        for emotion in graph_data.get("emotions", []):
            if isinstance(emotion, dict):
                emotions.append({
                    "type": emotion.get("type", ""),
                    "valence": emotion.get("valence", "neutral"),
                    "intensity": emotion.get("intensity", 3),
                    "value": f"{emotion.get('valence', 'neutral')} intensity {emotion.get('intensity', 3)}/5"  # Backward compat
                })
            else:
                emotions.append(emotion)
        
        # Extract events from graph data (already in graph_data)
        events = [{"name": event} for event in graph_data.get("events", [])]
        
        # Get relationships from graph data (already in graph_data)
        relationships = graph_data.get("relationships", [])
        
        # If no relationships extracted but we have entities, try to infer relationships as fallback
        if not relationships and len(entities) >= 2:
            logger.debug("No relationships extracted by LLM, attempting to infer relationships from entities")
            try:
                inferred_rels = self.infer_relationships(entities, text)
                # Convert inferred relationships to match graph_data format
                # Create a name-to-type mapping for better type inference
                entity_name_to_type = {}
                for ent in entities:
                    entity_name_to_type[ent.get("name", "")] = ent.get("type", "").upper()
                
                entity_type_mapping = {
                    "PERSON": "person",
                    "ORG": "organization",
                    "EVENT": "event",
                    "PLACE": "place",
                    "DATE": "date"
                }
                
                for rel in inferred_rels:
                    source = rel.get("source", "")
                    target = rel.get("target", "")
                    source_type_raw = entity_name_to_type.get(source, "PERSON")
                    target_type_raw = entity_name_to_type.get(target, "PERSON")
                    
                    relationships.append({
                        "from": source,
                        "to": target,
                        "type": rel.get("type", "related_to"),
                        "from_type": entity_type_mapping.get(source_type_raw, "person"),
                        "to_type": entity_type_mapping.get(target_type_raw, "person"),
                        "confidence": 0.5  # Lower confidence for inferred
                    })
                logger.info(f"Inferred {len(relationships)} relationships from entities")
            except Exception as e:
                logger.warning(f"Failed to infer relationships: {str(e)}")
        
        # Classify intent (separate LLM call - this is necessary)
        intent = self.classify_intent(text)
        
        return {
            "entities": entities,
            "events": events,
            "emotions": emotions,
            "intent": intent,
            "relationships": relationships,
            # Include raw graph data for advanced use cases
            "graph_data": graph_data
        }

# Global instance
nlu_service = NLUService()


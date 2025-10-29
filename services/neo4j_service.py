"""
Neo4j service for GraphRAG - Knowledge graph storage and retrieval
"""
import os
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Suppress Neo4j schema warnings when graph is empty
# These warnings are expected before any entries are saved and will disappear once data exists
neo4j_notification_logger = logging.getLogger("neo4j.notifications")
neo4j_notification_logger.setLevel(logging.ERROR)  # Only show errors, not warnings

class Neo4jService:
    """Service for Neo4j graph database operations"""
    
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        # Support both NEO4J_USERNAME (existing) and NEO4J_USER (guide) for backward compatibility
        self.username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD")
        
        if not self.uri or not self.password:
            logger.warning("Neo4j credentials not configured. GraphRAG features will be disabled.")
            self.driver = None
        else:
            self._initialize_driver()
            # Initialize schema constraints after driver is ready
            if self.driver:
                try:
                    self.initialize_schema()
                except Exception as e:
                    logger.warning(f"Schema initialization failed (may already exist): {str(e)}")
    
    def _initialize_driver(self):
        """Initialize or reinitialize the Neo4j driver"""
        try:
            # Close existing driver if it exists
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.close()
                except:
                    pass
            
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=10,
                connection_acquisition_timeout=60
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Neo4j connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            self.driver = None
    
    def _ensure_connection(self):
        """Ensure Neo4j connection is active, reconnect if needed"""
        if not self.driver:
            self._initialize_driver()
            return False
        
        try:
            # Test connection with a simple query
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            logger.warning(f"Neo4j connection test failed, reconnecting: {str(e)}")
            self._initialize_driver()
            return self.driver is not None
    
    def close(self):
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()
    
    def initialize_schema(self) -> Dict[str, Any]:
        """
        Initialize Neo4j schema with constraints
        Creates uniqueness constraints for key properties
        
        Returns:
            Dict with success status and created constraints
        """
        if not self.driver:
            return {
                "success": False,
                "error": "Neo4j not configured"
            }
        
        try:
            with self.driver.session() as session:
                constraints = [
                    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
                    "CREATE CONSTRAINT entry_id IF NOT EXISTS FOR (e:Entry) REQUIRE e.id IS UNIQUE",
                    "CREATE CONSTRAINT emotion_name IF NOT EXISTS FOR (em:Emotion) REQUIRE em.name IS UNIQUE",
                    "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
                    "CREATE CONSTRAINT organization_name IF NOT EXISTS FOR (o:Organization) REQUIRE o.name IS UNIQUE",
                    "CREATE CONSTRAINT event_name IF NOT EXISTS FOR (ev:Event) REQUIRE ev.name IS UNIQUE",
                    "CREATE CONSTRAINT place_name IF NOT EXISTS FOR (pl:Place) REQUIRE pl.name IS UNIQUE",
                    "CREATE CONSTRAINT date_name IF NOT EXISTS FOR (d:Date) REQUIRE d.name IS UNIQUE"
                ]
                
                created_constraints = []
                for constraint_stmt in constraints:
                    try:
                        session.run(constraint_stmt)
                        created_constraints.append(constraint_stmt.split("FOR")[0].strip().replace("CREATE CONSTRAINT ", "").replace(" IF NOT EXISTS", ""))
                        logger.debug(f"Created constraint: {constraint_stmt}")
                    except Exception as e:
                        # Constraint may already exist or have different syntax requirements
                        error_msg = str(e).lower()
                        if "already exists" in error_msg or "equivalent constraint" in error_msg:
                            logger.debug(f"Constraint already exists: {constraint_stmt.split('FOR')[0]}")
                        else:
                            logger.warning(f"Constraint creation warning: {str(e)}")
                
                logger.info(f"Schema initialization completed. Constraints: {len(created_constraints)}")
                return {
                    "success": True,
                    "constraints_created": created_constraints,
                    "message": "Schema initialized successfully"
                }
                
        except Exception as e:
            logger.error(f"Schema initialization error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def insert_entities_and_relationships(
        self, 
        user_id: str, 
        entry_id: str, 
        entities: List[Dict],
        relationships: List[Dict],
        emotions: List[Dict],
        events: List[Dict],
        summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Insert entities and relationships into Neo4j graph following the guide's schema
        
        Schema:
        - (User:user_id)-[:AUTHORED]->(Entry:entry_id)
        - (Entry)-[:FEELS]->(Emotion {name, valence, intensity})
        - (Entry)-[:MENTIONS]->(Person {name})
        - (Entry)-[:MENTIONS]->(Organization {name})
        - (Entry)-[:MENTIONS]->(Event {name})
        - (Entry)-[:MENTIONS]->(Place {name})
        - (Entry)-[:MENTIONS]->(Date {name})
        - (Person)-[:RELATES_TO {type}]->(Person)
        
        All entity types have unique constraints on their name property.
        
        Args:
            user_id: ID of the user
            entry_id: ID of the journal entry
            entities: List of entities with type, name, and properties
            relationships: List of relationships with from, to, type (or source, target for backward compat)
            emotions: List of emotions extracted (with type, valence, intensity)
            events: List of events extracted
            summary: Optional summary text for the entry
            
        Returns:
            Dict with success status and inserted counts
        """
        if not self.driver:
            return {
                "success": False,
                "error": "Neo4j not configured"
            }
        
        try:
            with self.driver.session() as session:
                result = session.execute_write(
                    self._insert_graph_tx,
                    user_id, entry_id, summary, entities, relationships, emotions, events
                )
                return result
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Insert entities error: {error_msg}")
            logger.error(f"Error details: {type(e).__name__}: {error_msg}", exc_info=True)
            
            # If connection error, try to reconnect once
            if "defunct connection" in error_msg or "connection" in error_msg.lower():
                logger.info("Attempting to reconnect to Neo4j...")
                self._initialize_driver()
                if self.driver:
                    # Retry once after reconnection
                    try:
                        return self.insert_entities_and_relationships(
                            user_id, entry_id, entities, relationships, emotions, events, summary
                        )
                    except Exception as retry_error:
                        logger.error(f"Retry after reconnection also failed: {str(retry_error)}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    def _insert_graph_tx(self, tx, user_id: str, entry_id: str, summary: Optional[str], 
                         entities: List[Dict], relationships: List[Dict], 
                         emotions: List[Dict], events: List[Dict]) -> Dict[str, Any]:
        """
        Transaction function for inserting graph data
        
        Args:
            tx: Neo4j transaction object
            user_id: ID of the user
            entry_id: ID of the journal entry
            summary: Optional summary text
            entities: List of entities
            relationships: List of relationships
            emotions: List of emotions
            events: List of events
            
        Returns:
            Dict with success status and inserted counts
        """
        entity_count = 0
        emotion_count = 0
        relationship_count = 0
        
        try:
            # Create User node and Entry node with :AUTHORED relationship
            tx.run("""
                MERGE (u:User {user_id: $user_id})
                MERGE (e:Entry {id: $entry_id})
                SET e.summary = $summary, 
                    e.user_id = $user_id,
                    e.timestamp = datetime()
                MERGE (u)-[:AUTHORED]->(e)
            """, user_id=user_id, entry_id=entry_id, summary=summary or "")
            
            # Categorize and insert entities by type
            # Map entity types to Neo4j labels
            entity_type_map = {
                "PERSON": "Person",
                "ORG": "Organization",
                "EVENT": "Event",
                "PLACE": "Place",
                "DATE": "Date",
                "TOPIC": None  # Topics can be stored as events or skipped - we'll handle separately
            }
            
            # Group entities by type, ensuring we capture all types
            entities_by_type = {}
            for entity in entities:
                entity_type = entity.get("type", "").upper()
                entity_name = entity.get("name", "").strip()
                
                if not entity_name:
                    continue
                
                neo4j_label = entity_type_map.get(entity_type)
                if neo4j_label:  # Only process if we have a label (skip TOPIC)
                    if neo4j_label not in entities_by_type:
                        entities_by_type[neo4j_label] = []
                    # Avoid duplicates within same type
                    if entity_name not in entities_by_type[neo4j_label]:
                        entities_by_type[neo4j_label].append(entity_name)
            
            # Also add events from the events list (backward compatibility)
            for event in events:
                event_name = event.get("name", "").strip() if isinstance(event, dict) else str(event).strip()
                if event_name:
                    if "Event" not in entities_by_type:
                        entities_by_type["Event"] = []
                    if event_name not in entities_by_type["Event"]:  # Avoid duplicates
                        entities_by_type["Event"].append(event_name)
            
            # Insert each entity type into appropriate node with proper relationships
            # Normalize names to lowercase for case-insensitive uniqueness
            for label, names in entities_by_type.items():
                for name in names:
                    if not name:
                        continue
                    # Normalize to lowercase for case-insensitive uniqueness
                    name_lower = name.lower().strip()
                    try:
                        # Use a single transaction to ensure atomicity
                        tx.run(f"""
                            MERGE (x:{label} {{name: $name_lower}})
                            SET x.original_name = COALESCE(x.original_name, $original_name)
                            WITH x
                            MATCH (e:Entry {{id: $entry_id, user_id: $user_id}})
                            MERGE (e)-[:MENTIONS]->(x)
                        """, name_lower=name_lower, original_name=name, entry_id=entry_id, user_id=user_id)
                        entity_count += 1
                    except Exception as e:
                        logger.error(f"Failed to insert {label} {name}: {str(e)}", exc_info=True)
                        # Continue with other entities
            
            # Insert Emotions with valence and intensity
            for emotion in emotions:
                emotion_type = emotion.get("type", "").strip()
                if not emotion_type:
                    continue
                
                # Get valence and intensity (with defaults)
                valence = emotion.get("valence", "neutral")
                intensity = emotion.get("intensity", 3)
                
                # Validate intensity is between 1-5
                try:
                    intensity = max(1, min(5, int(intensity)))
                except (ValueError, TypeError):
                    intensity = 3
                
                try:
                    # Normalize emotion name to lowercase for case-insensitive uniqueness
                    emotion_name_lower = emotion_type.lower().strip()
                    tx.run("""
                        MERGE (em:Emotion {name: $name_lower})
                        SET em.valence = $valence, 
                            em.intensity = $intensity,
                            em.original_name = COALESCE(em.original_name, $original_name)
                        WITH em
                        MATCH (e:Entry {id: $entry_id, user_id: $user_id})
                        MERGE (e)-[:FEELS]->(em)
                    """, name_lower=emotion_name_lower, original_name=emotion_type, valence=valence, intensity=intensity, entry_id=entry_id, user_id=user_id)
                    emotion_count += 1
                except Exception as e:
                    logger.error(f"Failed to insert emotion {emotion_type}: {str(e)}", exc_info=True)
                    # Continue with other emotions
            
            # Insert Relationships between typed entities
            # Build a map of entity names to their labels for quick lookup
            entity_name_to_label = {}
            for ent in entities:
                ent_name = (ent.get("name") or "").strip().lower()
                ent_type = (ent.get("type") or "").strip().upper()
                if ent_name and ent_type:
                    label = entity_type_map.get(ent_type)
                    if label:
                        entity_name_to_label[ent_name] = label
            
            for rel in relationships:
                # Support both "from/to" (guide format) and "source/target" (backward compat)
                source = (rel.get("from") or rel.get("source") or "").strip()
                target = (rel.get("to") or rel.get("target") or "").strip()
                rel_type = (rel.get("type") or "related_to").strip()
                from_type_raw = (rel.get("from_type") or "").strip().lower()
                to_type_raw = (rel.get("to_type") or "").strip().lower()
                
                if not source or not target:
                    continue
                
                # Map raw types to Neo4j labels
                type_label_map = {
                    "person": "Person",
                    "organization": "Organization",
                    "org": "Organization",
                    "event": "Event",
                    "place": "Place",
                    "date": "Date",
                    "user": "User"
                }
                
                from_label = type_label_map.get(from_type_raw)
                to_label = type_label_map.get(to_type_raw)
                
                # If labels missing, try to infer from entities list by name match (case-insensitive)
                source_lower = source.lower().strip()
                target_lower = target.lower().strip()
                
                if not from_label:
                    from_label = entity_name_to_label.get(source_lower)
                if not to_label:
                    to_label = entity_name_to_label.get(target_lower)
                
                # Skip if we can't determine both labels - relationship needs both nodes to exist
                if not from_label or not to_label:
                    logger.debug(f"Skipping relationship {source}->{target}: missing labels (from_type={from_type_raw}, to_type={to_type_raw})")
                    continue
                
                try:
                    # Use parameterized query with label variables to avoid injection issues
                    # MATCH both nodes first, then MERGE relationship
                    # Use dictionary for parameters since "from" is a Python keyword
                    result = tx.run(f"""
                        MATCH (a:{from_label} {{name: $from_lower}}), (b:{to_label} {{name: $to_lower}})
                        MERGE (a)-[r:RELATES_TO]->(b)
                        SET r.type = $type,
                            r.created_at = datetime()
                        RETURN r
                    """, {"from_lower": source_lower, "to_lower": target_lower, "type": rel_type})
                    
                    # Check if relationship was created
                    record = result.single()
                    if record:
                        relationship_count += 1
                        logger.debug(f"Created relationship: {source} ({from_label}) -[{rel_type}]-> {target} ({to_label})")
                    else:
                        logger.debug(f"Relationship not created: nodes not found - {source} ({from_label}) or {target} ({to_label})")
                except Exception as e:
                    # If relationship creation fails, log but continue
                    logger.warning(f"Failed to insert relationship {source}->{target} ({from_label}->{to_label}): {str(e)}")
                    logger.debug(f"Attempted: source={source_lower} ({from_label}), target={target_lower} ({to_label})", exc_info=True)
                    # Don't fail the entire transaction on relationship errors
                    continue
            
            logger.info(f"Inserted {entity_count} entities, {emotion_count} emotions, {relationship_count} relationships")
            
            return {
                "success": True,
                "entities_inserted": entity_count,
                "emotions_inserted": emotion_count,
                "relationships_inserted": relationship_count
            }
            
        except Exception as e:
            logger.error(f"Transaction error in _insert_graph_tx: {str(e)}")
            logger.error(f"Error details: {type(e).__name__}", exc_info=True)
            raise  # Re-raise to let Neo4j handle transaction rollback
    
    def query_related_entities(self, user_id: str, entity_name: str, limit: int = 5) -> Dict[str, Any]:
        """
        Query entities related to a given entity
        
        Args:
            user_id: ID of the user
            entity_name: Name of the entity to find relations for
            limit: Maximum number of related entities to return
            
        Returns:
            Dict containing related entities
        """
        if not self.driver:
            return {
                "success": False,
                "error": "Neo4j not configured",
                "related_entities": []
            }
        
        # Ensure connection is active
        if not self._ensure_connection():
            return {
                "success": False,
                "error": "Neo4j connection unavailable",
                "related_entities": []
            }
        
        try:
            with self.driver.session() as session:
                # Use OPTIONAL MATCH to avoid warnings when nodes don't exist
                # Normalize entity_name to lowercase for case-insensitive matching
                entity_name_lower = entity_name.lower().strip()
                result = session.run(
                    """
                    MATCH (e {{name: $entity_name_lower}})
                    WHERE e.user_id = $user_id OR e.user_id IS NULL
                    OPTIONAL MATCH (e)-[:RELATES_TO|MENTIONED_IN]-(related)
                    WHERE related IS NOT NULL 
                      AND (related.user_id = $user_id OR related.user_id IS NULL)
                    WITH related
                    WHERE related IS NOT NULL
                    RETURN DISTINCT related.name AS name, labels(related)[0] AS type
                    LIMIT $limit
                    """,
                    entity_name_lower=entity_name_lower,
                    user_id=user_id,
                    limit=limit
                )
                
                related_entities = []
                for record in result:
                    name = record.get("name")
                    entity_type = record.get("type")
                    if name and entity_type:
                        related_entities.append({
                            "name": name,
                            "type": entity_type
                        })
                
                return {
                    "success": True,
                    "related_entities": related_entities
                }
                
        except Exception as e:
            logger.error(f"Query related entities error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "related_entities": []
            }
    
    def get_user_graph_context(self, user_id: str, query_text: str, limit: int = 5) -> Dict[str, Any]:
        """
        Get graph-based context for a user's query
        
        Args:
            user_id: ID of the user
            query_text: Query text to find context for
            limit: Maximum number of entries to return
            
        Returns:
            Dict containing graph context
        """
        if not self.driver:
            return {
                "success": False,
                "error": "Neo4j not configured",
                "context": "",
                "entries": []
            }
        
        # Ensure connection is active
        if not self._ensure_connection():
            return {
                "success": False,
                "error": "Neo4j connection unavailable",
                "context": "",
                "entries": []
            }
        
        try:
            with self.driver.session() as session:
                # First check if any Entry nodes exist for this user
                # Use a simple query that won't trigger warnings if the label doesn't exist
                try:
                    # Try to get the count - if Entry label doesn't exist, this will return 0
                    count_result = session.run(
                        """
                        OPTIONAL MATCH (e:Entry {user_id: $user_id})
                        RETURN count(e) AS entry_count
                        """,
                        user_id=user_id
                    )
                    
                    entry_count = count_result.single()["entry_count"]
                    if entry_count == 0:
                        return {
                            "success": True,
                            "context": "",
                            "entries": []
                        }
                except Exception as e:
                    # If query fails (e.g., label doesn't exist), return empty context
                    logger.debug(f"Graph empty or Entry label doesn't exist: {str(e)}")
                    return {
                        "success": True,
                        "context": "",
                        "entries": []
                    }
                
                # Now we know Entry nodes exist, so we can safely query
                # GraphRAG: Find entities matching query, traverse relationships, and find related entries
                # Use case-insensitive matching with toLower() for better results
                query_lower = query_text.lower().strip()[:50]
                
                logger.info(f"Querying graph context for: '{query_text}' (lowercase: '{query_lower}')")
                
                # GraphRAG query: Traverse relationships to find related entities
                # Step 1: Find entities matching query (direct match)
                # Step 2: Traverse :RELATES_TO relationships to find neighbors (1 hop)
                # Step 3: Find entries mentioning any of these entities
                result = session.run(
                    """
                    // Step 1: Find entities that directly match the query
                    MATCH (matching_entity)
                    WHERE labels(matching_entity)[0] IN ['Person', 'Organization', 'Event', 'Place', 'Emotion']
                      AND matching_entity.name CONTAINS $query_lower
                    
                    // Step 2: Find entities related via RELATES_TO (1 hop in both directions)
                    OPTIONAL MATCH (matching_entity)-[:RELATES_TO]->(related_outbound)
                    OPTIONAL MATCH (related_inbound)-[:RELATES_TO]->(matching_entity)
                    
                    // Collect all entity names (matching + related)
                    WITH collect(DISTINCT matching_entity.name) AS direct_names,
                         collect(DISTINCT related_outbound.name) AS outbound_names,
                         collect(DISTINCT related_inbound.name) AS inbound_names
                    
                    // Combine into single list and filter nulls
                    WITH direct_names + outbound_names + inbound_names AS all_names
                    UNWIND all_names AS entity_name
                    WITH collect(DISTINCT entity_name) AS relevant_names
                    WHERE size(relevant_names) > 0
                    
                    // Step 3: Find entries that mention any of these entities
                    MATCH (e:Entry {user_id: $user_id})
                    OPTIONAL MATCH (e)-[:MENTIONS]->(mentioned_entity)
                    WHERE mentioned_entity.name IN relevant_names
                    
                    OPTIONAL MATCH (e)-[:FEELS]->(emotion:Emotion)
                    WHERE emotion.name IN relevant_names OR emotion.name CONTAINS $query_lower
                    
                    // Collect results
                    WITH e,
                         collect(DISTINCT emotion.name) AS emotions,
                         collect(DISTINCT mentioned_entity.name) AS entity_names,
                         collect(DISTINCT labels(mentioned_entity)[0]) AS entity_types,
                         e.timestamp AS timestamp
                    
                    // Filter to entries that have at least one match
                    WHERE size(entity_names) > 0 OR size(emotions) > 0
                    
                    RETURN DISTINCT e.id AS entry_id, 
                           e.summary AS summary,
                           emotions,
                           entity_names AS entities,
                           entity_types AS types,
                           timestamp
                    ORDER BY timestamp DESC
                    LIMIT $limit
                    """,
                    user_id=user_id,
                    query_lower=query_lower,
                    query_text=query_text.strip()[:50],
                    limit=limit
                )
                
                entries = []
                context_sentences = []
                
                # Log raw results for debugging
                raw_records = []
                for record in result:
                    raw_records.append({
                        "entry_id": record.get("entry_id"),
                        "summary": record.get("summary"),
                        "emotions": record.get("emotions"),
                        "entities": record.get("entities"),
                        "types": record.get("types"),
                        "timestamp": record.get("timestamp")
                    })
                
                logger.info(f"Raw graph query results: {len(raw_records)} entries found")
                for idx, rec in enumerate(raw_records):
                    logger.info(f"  Entry {idx + 1}: id={rec['entry_id']}, emotions={rec['emotions']}, entities={rec['entities']}, types={rec['types']}")
                
                # Also query for relationships to see what edges exist
                try:
                    rel_result = session.run("""
                        MATCH (e:Entry {user_id: $user_id})
                        OPTIONAL MATCH (e)-[:MENTIONS]->(entity)
                        OPTIONAL MATCH (entity)-[r:RELATES_TO]->(related)
                        WHERE entity IS NOT NULL 
                          AND (
                            entity.name CONTAINS $query_lower 
                            OR labels(entity)[0] CONTAINS $query_lower
                            OR entity.name = $query_lower
                          )
                        RETURN entity.name AS entity_name,
                               labels(entity)[0] AS entity_type,
                               type(r) AS rel_type,
                               r.type AS rel_type_prop,
                               related.name AS related_name,
                               labels(related)[0] AS related_type
                        LIMIT 20
                    """, user_id=user_id, query_lower=query_lower, query_text=query_text.strip()[:50])
                    
                    relationships_found = []
                    for rel_record in rel_result:
                        rel_info = {
                            "entity": rel_record.get("entity_name"),
                            "entity_type": rel_record.get("entity_type"),
                            "rel_type": rel_record.get("rel_type"),
                            "rel_type_prop": rel_record.get("rel_type_prop"),
                            "related": rel_record.get("related_name"),
                            "related_type": rel_record.get("related_type")
                        }
                        relationships_found.append(rel_info)
                    
                    logger.info(f"Relationships found: {len(relationships_found)}")
                    for rel_info in relationships_found:
                        logger.info(f"  Edge: {rel_info['entity']} ({rel_info['entity_type']}) -[{rel_info['rel_type'] or 'RELATES_TO'}: {rel_info['rel_type_prop']}]-> {rel_info['related']} ({rel_info['related_type']})")
                except Exception as rel_error:
                    logger.warning(f"Failed to query relationships: {str(rel_error)}")
                
                # Debug: Query all entries and their connections to see what's in the graph
                try:
                    # First, check ALL entries without user_id filter to see what exists
                    all_entries_check = session.run("""
                        MATCH (e:Entry)
                        RETURN e.id AS entry_id, e.user_id AS user_id, e.summary AS summary
                        LIMIT 10
                    """)
                    
                    logger.info("All Entry nodes in database (regardless of user):")
                    for entry_check in all_entries_check:
                        logger.info(f"  Entry id={entry_check.get('entry_id')}, user_id={entry_check.get('user_id')}, summary={entry_check.get('summary')[:30] if entry_check.get('summary') else 'None'}")
                    
                    all_nodes_result = session.run("""
                        MATCH (e:Entry {user_id: $user_id})
                        OPTIONAL MATCH (e)-[:FEELS]->(emotion:Emotion)
                        OPTIONAL MATCH (e)-[:MENTIONS]->(entity)
                        WITH e,
                             collect(DISTINCT emotion.name) AS all_emotions,
                             collect(DISTINCT entity.name) AS all_entities,
                             collect(DISTINCT labels(entity)[0]) AS all_types,
                             e.id AS entry_id,
                             e.summary AS summary,
                             e.user_id AS user_id,
                             e.timestamp AS timestamp
                        RETURN entry_id, summary, user_id, all_emotions AS emotions, 
                               all_entities AS entities, all_types AS types, timestamp
                        ORDER BY timestamp DESC
                        LIMIT 5
                    """, user_id=user_id)
                    
                    # Also check directly what entities exist in the graph
                    direct_entities_check = session.run("""
                        MATCH (e:Entry {user_id: $user_id})
                        OPTIONAL MATCH (e)-[:MENTIONS]->(entity)
                        OPTIONAL MATCH (e)-[:FEELS]->(emotion)
                        RETURN e.id AS entry_id,
                               collect(DISTINCT entity.name) AS entity_names,
                               collect(DISTINCT labels(entity)[0]) AS entity_labels,
                               collect(DISTINCT emotion.name) AS emotion_names
                        LIMIT 10
                    """, user_id=user_id)
                    
                    logger.info("Direct entity connections check:")
                    for direct_check in direct_entities_check:
                        logger.info(f"  Entry {direct_check.get('entry_id')}: entities={direct_check.get('entity_names')}, labels={direct_check.get('entity_labels')}, emotions={direct_check.get('emotion_names')}")
                    
                    # Check what entities actually exist in the graph (regardless of connection)
                    all_entities_check = session.run("""
                        MATCH (p:Person)
                        RETURN p.name AS name, 'Person' AS type
                        UNION
                        MATCH (o:Organization)
                        RETURN o.name AS name, 'Organization' AS type
                        UNION
                        MATCH (ev:Event)
                        RETURN ev.name AS name, 'Event' AS type
                        UNION
                        MATCH (pl:Place)
                        RETURN pl.name AS name, 'Place' AS type
                        UNION
                        MATCH (em:Emotion)
                        RETURN em.name AS name, 'Emotion' AS type
                        LIMIT 20
                    """)
                    
                    logger.info("All entities in graph:")
                    entity_count = 0
                    for ent_check in all_entities_check:
                        logger.info(f"  {ent_check.get('type')}: {ent_check.get('name')}")
                        entity_count += 1
                    logger.info(f"Total entities found: {entity_count}")
                    
                    all_nodes = []
                    for node_record in all_nodes_result:
                        all_nodes.append({
                            "entry_id": node_record.get("entry_id"),
                            "summary": node_record.get("summary"),
                            "user_id": node_record.get("user_id"),
                            "emotions": node_record.get("emotions"),
                            "entities": node_record.get("entities"),
                            "types": node_record.get("types")
                        })
                    
                    logger.info(f"All entries for user {user_id} in graph: {len(all_nodes)} entries")
                    for idx, node in enumerate(all_nodes):
                        logger.info(f"  Entry {idx + 1}: id={node['entry_id']}, user_id={node['user_id']}, summary={node['summary'][:50] if node['summary'] else 'None'}..., emotions={node['emotions']}, entities={node['entities']}, types={node['types']}")
                    
                    # Also check what nodes are actually connected
                    connections_result = session.run("""
                        MATCH (e:Entry {user_id: $user_id})
                        OPTIONAL MATCH (e)-[:FEELS]->(emotion)
                        OPTIONAL MATCH (e)-[:MENTIONS]->(entity)
                        WITH e.id AS entry_id,
                             count(DISTINCT emotion) AS emotion_count,
                             count(DISTINCT entity) AS entity_count,
                             collect(DISTINCT labels(entity)[0]) AS connected_labels,
                             e.timestamp AS timestamp
                        RETURN entry_id, emotion_count, entity_count, connected_labels, timestamp
                        ORDER BY timestamp DESC
                        LIMIT 5
                    """, user_id=user_id)
                    
                    logger.info("Connection counts:")
                    for conn_record in connections_result:
                        logger.info(f"  Entry {conn_record.get('entry_id')}: {conn_record.get('emotion_count')} emotions, {conn_record.get('entity_count')} entities, labels={conn_record.get('connected_labels')}")
                except Exception as all_nodes_error:
                    logger.warning(f"Failed to query all nodes: {str(all_nodes_error)}")
                
                # Process the entries
                for record in raw_records:
                    entry_id = record.get("entry_id")
                    summary = record.get("summary") or ""
                    emotions = [e for e in (record.get("emotions") or []) if e]
                    entities = [e for e in (record.get("entities") or []) if e]
                    entity_types = [t for t in (record.get("types") or []) if t]
                    timestamp = record.get("timestamp")
                    
                    if not entry_id:
                        continue
                    
                    # Format timestamp for display
                    timestamp_str = ""
                    if timestamp:
                        try:
                            # Parse Neo4j datetime and format nicely
                            if isinstance(timestamp, str):
                                timestamp_str = timestamp[:10]  # Just the date part
                            else:
                                timestamp_str = str(timestamp)[:10]
                        except:
                            timestamp_str = ""
                    
                    # Build context sentence
                    parts = []
                    if timestamp_str:
                        parts.append(f"On {timestamp_str}")
                    
                    if emotions:
                        emotion_str = ", ".join(emotions[:2])  # Max 2 emotions
                        if len(emotions) > 2:
                            emotion_str += f" and {len(emotions) - 2} more"
                        if timestamp_str:
                            parts.append(f"you mentioned feeling {emotion_str}")
                        else:
                            parts.append(f"You mentioned feeling {emotion_str}")
                    
                    if entities:
                        # Group entities by type for better context
                        people = [e for e, t in zip(entities, entity_types) if t == "Person"]
                        orgs = [e for e, t in zip(entities, entity_types) if t == "Organization"]
                        places = [e for e, t in zip(entities, entity_types) if t == "Place"]
                        
                        entity_parts = []
                        if people:
                            people_str = ", ".join(people[:2])
                            if len(people) > 2:
                                people_str += f" and {len(people) - 2} more"
                            entity_parts.append(people_str)
                        if orgs:
                            orgs_str = ", ".join(orgs[:2])
                            if len(orgs) > 2:
                                orgs_str += f" and {len(orgs) - 2} more"
                            entity_parts.append(orgs_str)
                        if places:
                            places_str = ", ".join(places[:2])
                            if len(places) > 2:
                                places_str += f" and {len(places) - 2} more"
                            entity_parts.append(places_str)
                        
                        if entity_parts:
                            entity_str = ", ".join(entity_parts)
                            if emotions:
                                parts.append(f"about {entity_str}")
                            else:
                                if timestamp_str:
                                    parts.append(f"you mentioned {entity_str}")
                                else:
                                    parts.append(f"You mentioned {entity_str}")
                    
                    # Combine into sentence
                    if parts:
                        sentence = " ".join(parts) + "."
                        context_sentences.append(sentence)
                    
                    entries.append({
                        "entry_id": entry_id,
                        "summary": summary,
                        "emotions": emotions,
                        "entities": entities,
                        "types": entity_types,
                        "timestamp": timestamp_str if timestamp_str else None
                    })
                
                # Format combined context
                if context_sentences:
                    # Combine multiple sentences naturally
                    if len(context_sentences) == 1:
                        context = context_sentences[0]
                    elif len(context_sentences) == 2:
                        context = f"{context_sentences[0]} {context_sentences[1]}"
                    else:
                        context = f"{context_sentences[0]} Also, {context_sentences[1]}"
                        if len(context_sentences) > 2:
                            context += f" And {len(context_sentences) - 2} more related entry{'s' if len(context_sentences) - 2 > 1 else ''}."
                    
                    logger.info(f"GraphRAG found {len(entries)} entries with context")
                else:
                    context = ""
                    logger.debug(f"No matching entries found for query: {query_text}")
                
                return {
                    "success": True,
                    "context": context,
                    "entries": entries,
                    "entity_count": sum(len(e.get("entities", [])) for e in entries)
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Get user graph context error: {error_msg}")
            
            # If connection error, try to reconnect once
            if "defunct connection" in error_msg or "connection" in error_msg.lower():
                logger.info("Attempting to reconnect to Neo4j...")
                self._initialize_driver()
                if self.driver:
                    # Retry once after reconnection
                    try:
                        return self.get_user_graph_context(user_id, query_text, limit)
                    except Exception as retry_error:
                        logger.error(f"Retry after reconnection also failed: {str(retry_error)}")
            
            return {
                "success": False,
                "error": error_msg,
                "context": "",
                "entries": []
            }
    
    def _map_entity_type_to_label(self, entity_type: str) -> str:
        """
        Map spaCy entity types to Neo4j node labels
        
        Args:
            entity_type: spaCy entity type (PERSON, ORG, GPE, etc.)
            
        Returns:
            Neo4j node label
        """
        mapping = {
            "PERSON": "Person",
            "ORG": "Organization",
            "GPE": "Place",
            "LOC": "Place",
            "EVENT": "Event",
            "PRODUCT": "Product",
            "WORK_OF_ART": "WorkOfArt",
            "MONEY": "Money",
            "DATE": "Date",
            "TIME": "Time"
        }
        
        return mapping.get(entity_type, "Entity")
    
    def create_indexes(self) -> Dict[str, Any]:
        """
        Create indexes for better query performance
        
        Returns:
            Dict with success status
        """
        if not self.driver:
            return {
                "success": False,
                "error": "Neo4j not configured"
            }
        
        try:
            with self.driver.session() as session:
                indexes = [
                    "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
                    "CREATE INDEX place_name IF NOT EXISTS FOR (p:Place) ON (p.name)",
                    "CREATE INDEX emotion_type IF NOT EXISTS FOR (e:Emotion) ON (e.type)",
                    "CREATE INDEX entry_id IF NOT EXISTS FOR (e:Entry) ON (e.id)",
                    "CREATE INDEX entry_user_id IF NOT EXISTS FOR (e:Entry) ON (e.user_id)"
                ]
                
                for index_query in indexes:
                    try:
                        session.run(index_query)
                    except Exception as e:
                        logger.warning(f"Index creation warning: {str(e)}")
                
                return {
                    "success": True,
                    "message": "Indexes created successfully"
                }
                
        except Exception as e:
            logger.error(f"Create indexes error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
neo4j_service = Neo4jService()


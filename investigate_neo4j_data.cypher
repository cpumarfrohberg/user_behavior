// ============================================
// Neo4j Data Investigation Queries
// ============================================
// Run these queries in Neo4j Browser or cypher-shell to investigate
// where your data went after the ETL dump

// ============================================
// 1. COUNT ALL NODES BY TYPE
// ============================================
// This will show you the total count of each node type in the database
MATCH (n)
RETURN labels(n)[0] AS node_type, count(n) AS count
ORDER BY count DESC;

// ============================================
// 2. COUNT ALL RELATIONSHIPS BY TYPE
// ============================================
// This will show you all relationship types and their counts
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(r) AS count
ORDER BY count DESC;

// ============================================
// 3. DETAILED NODE COUNTS WITH SAMPLE IDs
// ============================================
// Get detailed counts and sample IDs for each node type
MATCH (q:Question)
WITH count(q) AS question_count, collect(q.question_id)[0..10] AS sample_question_ids
RETURN 'Question' AS node_type, question_count AS count, sample_question_ids AS sample_ids
UNION ALL
MATCH (u:User)
WITH count(u) AS user_count, collect(u.user_id)[0..10] AS sample_user_ids
RETURN 'User' AS node_type, user_count AS count, sample_user_ids AS sample_ids
UNION ALL
MATCH (a:Answer)
WITH count(a) AS answer_count, collect(a.answer_id)[0..10] AS sample_answer_ids
RETURN 'Answer' AS node_type, answer_count AS count, sample_answer_ids AS sample_ids
UNION ALL
MATCH (c:Comment)
WITH count(c) AS comment_count, collect(c.comment_id)[0..10] AS sample_comment_ids
RETURN 'Comment' AS node_type, comment_count AS count, sample_comment_ids AS sample_ids
UNION ALL
MATCH (t:Tag)
WITH count(t) AS tag_count, collect(t.name)[0..10] AS sample_tag_names
RETURN 'Tag' AS node_type, tag_count AS count, sample_tag_names AS sample_ids;

// ============================================
// 4. CHECK FOR DUPLICATE IDs (should be 0 due to constraints)
// ============================================
// This checks if uniqueness constraints are working properly
MATCH (q:Question)
WITH q.question_id AS qid, count(q) AS cnt
WHERE cnt > 1
RETURN 'Duplicate Question IDs' AS issue, qid, cnt
UNION ALL
MATCH (u:User)
WITH u.user_id AS uid, count(u) AS cnt
WHERE cnt > 1
RETURN 'Duplicate User IDs' AS issue, uid, cnt
UNION ALL
MATCH (a:Answer)
WITH a.answer_id AS aid, count(a) AS cnt
WHERE cnt > 1
RETURN 'Duplicate Answer IDs' AS issue, aid, cnt;

// ============================================
// 5. CHECK CONSTRAINTS AND INDEXES
// ============================================
// Verify that uniqueness constraints exist
SHOW CONSTRAINTS;

// ============================================
// 6. SAMPLE QUESTION WITH ALL RELATIONSHIPS
// ============================================
// Get a sample question and all its connected nodes
MATCH (q:Question)
OPTIONAL MATCH (q)-[:HAS_TAG]->(t:Tag)
OPTIONAL MATCH (q)-[:HAS_ANSWER]->(a:Answer)
OPTIONAL MATCH (q)-[:HAS_COMMENT]->(c:Comment)
OPTIONAL MATCH (u:User)-[:ASKED]->(q)
WITH q, collect(DISTINCT t.name) AS tags, count(DISTINCT a) AS answer_count,
     count(DISTINCT c) AS comment_count, collect(DISTINCT u.display_name) AS askers
RETURN q.question_id, q.title, q.site, tags, answer_count, comment_count, askers
LIMIT 5;

// ============================================
// 7. CHECK FOR ISOLATED NODES (nodes without relationships)
// ============================================
// Find nodes that exist but have no relationships
MATCH (q:Question)
WHERE NOT (q)--()
RETURN 'Isolated Question' AS node_type, q.question_id AS id, q.title AS title
LIMIT 10
UNION ALL
MATCH (a:Answer)
WHERE NOT (a)--()
RETURN 'Isolated Answer' AS node_type, a.answer_id AS id, null AS title
LIMIT 10
UNION ALL
MATCH (u:User)
WHERE NOT (u)--()
RETURN 'Isolated User' AS node_type, u.user_id AS id, u.display_name AS title
LIMIT 10;

// ============================================
// 8. CHECK DATA BY SITE (if multiple sites)
// ============================================
// Group questions by site to see if data is filtered by site
MATCH (q:Question)
RETURN q.site AS site, count(q) AS question_count
ORDER BY question_count DESC;

// ============================================
// 9. CHECK RECENT COLLECTED DATA
// ============================================
// See the range of collected_at timestamps
MATCH (q:Question)
RETURN min(q.collected_at) AS earliest_collection,
       max(q.collected_at) AS latest_collection,
       count(q) AS total_questions;

// ============================================
// 10. FULL GRAPH STATISTICS
// ============================================
// Get comprehensive statistics about the entire graph
MATCH (n)
WITH count(n) AS total_nodes
MATCH ()-[r]->()
WITH total_nodes, count(r) AS total_relationships
MATCH (q:Question)
WITH total_nodes, total_relationships, count(q) AS questions
MATCH (u:User)
WITH total_nodes, total_relationships, questions, count(u) AS users
MATCH (a:Answer)
WITH total_nodes, total_relationships, questions, users, count(a) AS answers
MATCH (c:Comment)
WITH total_nodes, total_relationships, questions, users, answers, count(c) AS comments
MATCH (t:Tag)
RETURN total_nodes, total_relationships, questions, users, answers, comments, count(t) AS tags;

// ============================================
// 11. CHECK IF DATA EXISTS BUT IS FILTERED
// ============================================
// Check if there are questions with null or empty required fields
MATCH (q:Question)
WHERE q.question_id IS NULL OR q.title IS NULL
RETURN 'Question with null fields' AS issue, count(q) AS count
UNION ALL
MATCH (a:Answer)
WHERE a.answer_id IS NULL
RETURN 'Answer with null ID' AS issue, count(a) AS count
UNION ALL
MATCH (u:User)
WHERE u.user_id IS NULL
RETURN 'User with null ID' AS issue, count(u) AS count;

// ============================================
// 12. VERIFY RELATIONSHIP INTEGRITY
// ============================================
// Check if relationships point to non-existent nodes
MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
WITH count(DISTINCT q) AS questions_with_answers, count(DISTINCT a) AS unique_answers
MATCH (q2:Question)
RETURN questions_with_answers, unique_answers, count(q2) AS total_questions,
       CASE WHEN count(q2) > 0
            THEN toFloat(questions_with_answers) / count(q2) * 100
            ELSE 0 END AS pct_questions_with_answers;

// ============================================
// EXPLORE YOUR NEO4J DATA
// ============================================
// Use these queries to explore your data in Neo4j Browser
// The graph view only shows a limited number of nodes, but all data is there!

// ============================================
// 1. VIEW A SAMPLE QUESTION WITH FULL CONTEXT
// ============================================
// This will show one question with all its relationships
// Perfect for visualizing in the graph view
MATCH (q:Question)
OPTIONAL MATCH (u:User)-[:ASKED]->(q)
OPTIONAL MATCH (q)-[:HAS_TAG]->(t:Tag)
OPTIONAL MATCH (q)-[:HAS_ANSWER]->(a:Answer)
OPTIONAL MATCH (q)-[:HAS_COMMENT]->(c:Comment)
OPTIONAL MATCH (a)<-[:ANSWERED]-(au:User)
OPTIONAL MATCH (a)-[:HAS_COMMENT]->(ac:Comment)
RETURN q, u, t, a, c, au, ac
LIMIT 1;

// ============================================
// 2. FIND QUESTIONS WITH MOST ANSWERS
// ============================================
// See which questions have the most engagement
MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
WITH q, count(a) AS answer_count
ORDER BY answer_count DESC
RETURN q.question_id, q.title, q.site, answer_count
LIMIT 20;

// ============================================
// 3. FIND MOST ACTIVE USERS
// ============================================
// Users who asked questions, answered, and commented
MATCH (u:User)
OPTIONAL MATCH (u)-[:ASKED]->(q:Question)
OPTIONAL MATCH (u)-[:ANSWERED]->(a:Answer)
OPTIONAL MATCH (u)-[:COMMENTED]->(c:Comment)
WITH u,
     count(DISTINCT q) AS questions_asked,
     count(DISTINCT a) AS answers_given,
     count(DISTINCT c) AS comments_made
WHERE questions_asked > 0 OR answers_given > 0 OR comments_made > 0
RETURN u.user_id, u.display_name, u.reputation,
       questions_asked, answers_given, comments_made,
       (questions_asked + answers_given + comments_made) AS total_activity
ORDER BY total_activity DESC
LIMIT 20;

// ============================================
// 4. FIND MOST POPULAR TAGS
// ============================================
// Tags used by the most questions
MATCH (t:Tag)<-[:HAS_TAG]-(q:Question)
WITH t, count(q) AS question_count
ORDER BY question_count DESC
RETURN t.name AS tag, question_count
LIMIT 30;

// ============================================
// 5. QUESTIONS BY SITE
// ============================================
// Distribution of questions across different StackExchange sites
MATCH (q:Question)
RETURN q.site AS site, count(q) AS question_count
ORDER BY question_count DESC;

// ============================================
// 6. QUESTIONS WITH ACCEPTED ANSWERS
// ============================================
// Questions that have accepted answers
MATCH (q:Question)-[:ACCEPTED]->(a:Answer)
RETURN q.question_id, q.title, q.site, a.answer_id, a.score
LIMIT 20;

// ============================================
// 7. FULL QUESTION DETAILS (Table View)
// ============================================
// Get detailed information about questions in table format
MATCH (q:Question)
OPTIONAL MATCH (q)-[:HAS_ANSWER]->(a:Answer)
OPTIONAL MATCH (q)-[:HAS_TAG]->(t:Tag)
OPTIONAL MATCH (u:User)-[:ASKED]->(q)
WITH q,
     count(DISTINCT a) AS answer_count,
     collect(DISTINCT t.name) AS tags,
     collect(DISTINCT u.display_name)[0] AS asker
RETURN q.question_id, q.title, q.site, q.score,
       answer_count, tags, asker
ORDER BY q.score DESC
LIMIT 50;

// ============================================
// 8. EXPLORE A SPECIFIC QUESTION BY ID
// ============================================
// Replace 'YOUR_QUESTION_ID' with an actual question_id
// MATCH (q:Question {question_id: YOUR_QUESTION_ID})
// OPTIONAL MATCH path = (q)-[*1..2]-(connected)
// RETURN path;

// ============================================
// 9. GRAPH VISUALIZATION - SMALL SUBSET
// ============================================
// Use this to visualize a small, connected subgraph
// This is what you'll see in the graph view
MATCH path = (q:Question)-[*1..2]-(connected)
WHERE q.question_id IN [
    // Get IDs of questions with most activity
    (MATCH (q2:Question)-[:HAS_ANSWER]->(a:Answer)
     WITH q2, count(a) AS cnt
     ORDER BY cnt DESC
     LIMIT 3
     RETURN q2.question_id)
]
RETURN path
LIMIT 100;

// ============================================
// 10. STATISTICS SUMMARY
// ============================================
// Overall statistics about your graph
MATCH (q:Question)
WITH count(q) AS total_questions
MATCH (u:User)
WITH total_questions, count(u) AS total_users
MATCH (a:Answer)
WITH total_questions, total_users, count(a) AS total_answers
MATCH (c:Comment)
WITH total_questions, total_users, total_answers, count(c) AS total_comments
MATCH (t:Tag)
WITH total_questions, total_users, total_answers, total_comments, count(t) AS total_tags
MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
WITH total_questions, total_users, total_answers, total_comments, total_tags,
     count(DISTINCT q) AS questions_with_answers
MATCH (q:Question)-[:HAS_TAG]->(t:Tag)
RETURN
    total_questions,
    total_users,
    total_answers,
    total_comments,
    total_tags,
    questions_with_answers,
    round(toFloat(questions_with_answers) / total_questions * 100, 2) AS pct_questions_with_answers;

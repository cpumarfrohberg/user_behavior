// ============================================
// QUICK DIAGNOSTIC - Run this first!
// ============================================

// 1. Quick node counts
MATCH (n)
RETURN labels(n)[0] AS type, count(n) AS count
ORDER BY count DESC;

// 2. Check current database
CALL db.info() YIELD name, currentStatus
RETURN name AS database_name, currentStatus;

// 3. List all databases (if you have permissions)
SHOW DATABASES;

// 4. Sample of what's actually in the graph
MATCH (q:Question)
RETURN q.question_id, q.title, q.site
LIMIT 10;

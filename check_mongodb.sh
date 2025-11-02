#!/bin/bash
echo "🔍 Finding MongoDB container..."
CONTAINER=$(docker ps --filter "name=mongo" --format "{{.Names}}" | head -1)

if [ -z "$CONTAINER" ]; then
    echo "❌ No MongoDB container found"
    exit 1
fi

echo "✅ Found container: $CONTAINER"
echo ""
echo "📊 Listing all databases and collections..."
docker exec -it $CONTAINER mongosh --quiet --eval "
print('=== Databases ===');
db.adminCommand('listDatabases').databases.forEach(d => print('  - ' + d.name + ' (' + (d.sizeOnDisk / 1024 / 1024).toFixed(2) + ' MB)'));

print();
print('=== Collections ===');
db.adminCommand('listDatabases').databases.forEach(d => {
  let dbName = d.name;
  db.getSiblingDB(dbName).getCollectionNames().forEach(c => {
    let count = db.getSiblingDB(dbName).getCollection(c).countDocuments();
    print(dbName + '.' + c + ': ' + count + ' documents');
  });
});

print();
print('=== Checking stackexchange.questions ===');
let questions = db.getSiblingDB('stackexchange').getCollection('questions').countDocuments();
print('Questions: ' + questions);

if (questions > 0) {
  let sample = db.getSiblingDB('stackexchange').getCollection('questions').findOne();
  print('Sample question:');
  print('  ID: ' + sample.question_id);
  print('  Title: ' + sample.title.substring(0, 60) + '...');
  print('  Answers: ' + (sample.answers ? sample.answers.length : 0));
  print('  Comments: ' + (sample.comments ? sample.comments.length : 0));
  print('  Tags: ' + (sample.tags ? sample.tags.join(', ') : 'none'));
}
"

# Implementation Plan: Incremental Storage for StackExchange Collector

## Goal
Change the collector to store questions in MongoDB incrementally (as each page is fetched) instead of batching everything at the end.

---

## Step 1: Modify `search_questions()` Method

**File:** `stream_stackexchange/collector.py`

**Current behavior:**
- Collects all questions in `all_questions` list
- Returns list at the end
- No storage during collection

**Changes needed:**
1. Remove `all_questions = []` accumulation
2. Add `total_stored = 0` counter
3. After processing each page, store immediately:
   - Extract relevant questions from current page
   - Call `self.storage.store_questions(page_questions)` immediately
   - Track `total_stored += stored_count`
   - Print progress: `💾 Stored {stored_count} questions from page {page} (total: {total_stored})`
4. Change return type: Return `int` (total stored count) instead of `list[Question]`
5. Update docstring to reflect new behavior

**Code structure:**
```python
def search_questions(...) -> int:  # Changed return type
    total_stored = 0
    for page in range(1, pages + 1):
        # ... fetch page ...
        # ... validate and extract questions ...

        # Store immediately after processing page
        if page_questions:  # List of Question objects from this page
            stored_count = self.storage.store_questions(page_questions)
            total_stored += stored_count
            print(f"   💾 Stored {stored_count} questions (total: {total_stored})")

    return total_stored  # Return count instead of list
```

---

## Step 2: Simplify `collect_and_store()` Method

**File:** `stream_stackexchange/collector.py`

**Current behavior:**
- Calls `search_questions()` to get list
- Then stores all at once

**Changes needed:**
1. `search_questions()` now handles storage, so simplify this method
2. Change: `questions = self.search_questions(...)` → `total_stored = self.search_questions(...)`
3. Remove the `if questions:` block that calls `store_questions()`
4. Update final print: `print(f"✅ Total stored: {total_stored} documents")`
5. Update docstring

**Code structure:**
```python
def collect_and_store(...):
    total_stored = self.search_questions(site, tag, pages)  # Already stores as it goes
    print(f"✅ Total stored: {total_stored} documents")
```

---

## Step 3: Improve Error Handling

**File:** `stream_stackexchange/collector.py`

**Current behavior:**
- If one page fails, continues but might lose context
- All-or-nothing storage

**Changes needed:**
1. Wrap storage call in try-except per page
2. Continue to next page if storage fails for one page
3. Log which pages failed
4. Return partial success (count of successfully stored pages)
5. Add error logging: `print(f"⚠️  Error storing page {page}: {e}")`

**Code structure:**
```python
for page in range(1, pages + 1):
    try:
        # ... fetch and process page ...
        if page_questions:
            try:
                stored_count = self.storage.store_questions(page_questions)
                total_stored += stored_count
            except Exception as e:
                print(f"⚠️  Error storing page {page}: {e}")
                # Continue to next page
    except Exception as e:
        print(f"Error fetching page {page}: {e}")
        continue  # Already exists, keep it
```

---

## Step 4: Update Progress Messages

**File:** `stream_stackexchange/collector.py`

**Changes needed:**
1. Add storage progress message after each page
2. Show running total: `(total: {total_stored})`
3. Add summary at end with final count
4. Keep existing fetch/validation messages

**New messages:**
- `💾 Stored {count} questions from page {page} (total: {total})`
- `✅ Collection complete: {total} documents stored`

---

## Step 5: Optional - Add Resume Capability (Future Enhancement)

**Not required for basic incremental storage, but could be added:**

**Changes needed:**
1. Track last successful page in a file or MongoDB
2. Add `--resume` flag to skip already-fetched pages
3. Check which pages already exist in MongoDB
4. Start from last page + 1

**This is optional and can be done later.**

---

## Step 6: Testing

**Test cases:**
1. Normal collection: Verify questions stored after each page
2. Partial failure: Verify successful pages are stored even if later pages fail
3. Empty pages: Verify no errors when a page returns 0 questions
4. Duplicate handling: Verify existing duplicate logic still works
5. Memory usage: Verify lower memory usage (no large list accumulation)

---

## Summary of File Changes

**File: `stream_stackexchange/collector.py`**

1. **`search_questions()` method:**
   - Change return type: `list[Question]` → `int`
   - Remove `all_questions` list accumulation
   - Add `total_stored` counter
   - Store after each page: `self.storage.store_questions(page_questions)`
   - Return `total_stored` instead of list
   - Update docstring

2. **`collect_and_store()` method:**
   - Simplify: `total_stored = self.search_questions(...)`
   - Remove `if questions:` block
   - Update final print message
   - Update docstring

3. **Error handling:**
   - Add try-except around storage call per page
   - Continue on storage errors
   - Log storage failures

4. **Progress messages:**
   - Add storage progress after each page
   - Show running totals

**No changes needed:**
- `storage.py` - Already handles lists correctly
- `main()` function - No changes needed
- Other files - No changes needed

---

## Benefits After Implementation

✅ **Immediate visibility**: Data appears in MongoDB as it's collected
✅ **Failure recovery**: Successful pages are saved even if later pages fail
✅ **Lower memory**: No large list accumulation
✅ **Progress tracking**: See exactly how many stored per page
✅ **Better UX**: Can monitor progress in real-time

---

## Implementation Order

1. Modify `search_questions()` to store incrementally
2. Simplify `collect_and_store()`
3. Add error handling around storage
4. Update progress messages
5. Test with small page count (e.g., 2 pages)
6. Test with full collection

---

## Detailed Code Changes

### Current `search_questions()` method (lines 24-83):

```python
def search_questions(
    self,
    site: str | None = None,
    tag: str | None = None,
    pages: int = DEFAULT_PAGES,
) -> list[Question]:  # CHANGE: Return int instead
    """
    Search and extract questions from StackExchange

    Args:
        site: StackExchange site (default: DEFAULT_SITE)
        tag: Tag to filter by (default: DEFAULT_TAG)
        pages: Number of pages to fetch (default: DEFAULT_PAGES)

    Returns:
        Number of questions stored (int)  # CHANGE: Update docstring
    """
    site = site or DEFAULT_SITE
    tag = tag or DEFAULT_TAG

    total_stored = 0  # CHANGE: Replace all_questions = []

    for page in range(1, pages + 1):
        try:
            print(f"   🔍 Fetching page {page}...")
            print(f"   📋 Site: {site}, Tag: {tag}")

            # Fetch questions from API
            data = self.api_client.get_questions(site, tag, page)
            questions = data.get("items", [])

            print(f"   📄 Found {len(questions)} questions on page {page}")

            if questions:
                # Show sample question for debugging
                sample = questions[0]
                print(
                    f"   📝 Sample title: {sample.get('title', 'No title')[:60]}..."
                )
                print(f"   🏷️  Sample tags: {sample.get('tags', [])}")

            page_questions = []  # NEW: Collect questions for this page only
            relevant_count = 0
            for question_dict in questions:
                # Validate relevance
                if not is_relevant(question_dict):
                    continue

                # Extract question data
                question = extract_question(question_dict, site, self.api_client)
                if question:
                    page_questions.append(question)  # CHANGE: Append to page_questions
                    relevant_count += 1

            print(f"   ✅ {relevant_count} questions passed relevance filter")

            # NEW: Store immediately after processing page
            if page_questions:
                try:
                    stored_count = self.storage.store_questions(page_questions)
                    total_stored += stored_count
                    print(f"   💾 Stored {stored_count} questions from page {page} (total: {total_stored})")
                except Exception as e:
                    print(f"   ⚠️  Error storing page {page}: {e}")
                    # Continue to next page even if storage fails

        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            continue

    return total_stored  # CHANGE: Return count instead of all_questions
```

### Current `collect_and_store()` method (lines 85-105):

```python
def collect_and_store(
    self,
    site: str | None = None,
    tag: str | None = None,
    pages: int = DEFAULT_PAGES,
):
    """
    Collect questions and store in MongoDB

    Args:
        site: StackExchange site
        tag: Tag to filter by
        pages: Number of pages to fetch
    """
    total_stored = self.search_questions(site, tag, pages)  # CHANGE: Get count, not list

    # CHANGE: Remove if questions block, storage already happened
    if total_stored > 0:
        print(f"✅ Total stored: {total_stored} documents")
    else:
        print("No questions collected")
```

---

## Notes

- The `storage.py` file doesn't need changes - it already handles lists correctly
- The `main()` function doesn't need changes
- This is a backward-compatible change in terms of functionality (same end result)
- The main difference is when storage happens (incremental vs batch)

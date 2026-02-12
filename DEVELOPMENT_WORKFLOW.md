# Field Trainer Development Workflow
**Best Practices to Avoid Database Schema Issues**

---

## The Problem We're Solving

**Schema Drift:** Code expects database columns that don't exist in the committed database file.

**Root Cause:**
1. Developer adds column manually: `ALTER TABLE sessions ADD COLUMN pattern_config TEXT`
2. Code works locally with manual column
3. Code gets committed
4. Database file gets committed WITHOUT the column
5. Fresh install or git reset → ERROR (column missing)

---

## Solution: Use the Migration System

### ✅ CORRECT Workflow (With Migrations)

**When you need to add a database column:**

1. **Add migration to `/opt/field_trainer/db_migrations.py`:**
   ```python
   MIGRATIONS = [
       # ... existing migrations ...

       # Migration 003: Your new column
       {
           'version': 3,
           'name': 'add_my_new_column',
           'sql': '''
               ALTER TABLE my_table ADD COLUMN my_column TEXT
           ''',
           'check': "SELECT COUNT(*) FROM pragma_table_info('my_table') WHERE name='my_column'"
       },
   ]
   ```

2. **Restart the server** (migrations run automatically on startup):
   ```bash
   sudo pkill -f field_trainer_main.py
   python3 field_trainer_main.py --host 0.0.0.0 --port 5000 --debug 0
   ```

3. **Verify migration applied:**
   ```bash
   python3 /opt/field_trainer/db_migrations.py
   # Should show: Current schema version: 3
   ```

4. **Test your feature** to ensure it works

5. **Commit BOTH code and migration:**
   ```bash
   git add field_trainer/db_migrations.py
   git add your_feature_code.py
   git commit -m "Add feature X with database migration"
   ```

**Benefits:**
- ✅ Migration runs automatically on any machine
- ✅ No manual ALTER TABLE needed
- ✅ No schema drift between dev/prod
- ✅ Database file in git doesn't matter (migrations fix it)

---

### ❌ INCORRECT Workflow (Manual ALTER)

**DON'T DO THIS:**
```bash
# ❌ BAD: Manually alter database
sqlite3 /opt/data/field_trainer.db
> ALTER TABLE sessions ADD COLUMN pattern_config TEXT;

# ❌ BAD: Code works locally, commit it
git add routes/sessions_bp.py
git commit -m "Add pattern config feature"

# ❌ RESULT: Works on your machine, breaks everywhere else!
```

---

## Alternative: Update CREATE TABLE (Simpler for Small Projects)

If you don't want migrations, always update the CREATE TABLE statement:

1. **Edit `/opt/field_trainer/db_manager.py`:**
   ```python
   CREATE TABLE IF NOT EXISTS sessions (
       session_id TEXT PRIMARY KEY,
       ...
       pattern_config TEXT,  # ← ADD NEW COLUMN HERE
       ...
   )
   ```

2. **Delete database to force recreation:**
   ```bash
   rm /opt/data/field_trainer.db
   ```

3. **Restart server** (creates fresh database with new schema)

4. **Commit updated CREATE TABLE:**
   ```bash
   git add field_trainer/db_manager.py
   git commit -m "Add pattern_config column to sessions"
   ```

**Trade-offs:**
- ✅ Simple and straightforward
- ❌ Loses all data when you delete database
- ❌ Requires manual steps

---

## Migration System Reference

### How It Works

1. **Startup:** Server calls `apply_migrations()` automatically
2. **Check:** Migrations table tracks which migrations already ran
3. **Apply:** Only runs migrations that haven't been applied yet
4. **Safe:** If column already exists (manual add), just records it

### Migration File Structure

```python
{
    'version': 1,              # Unique sequential number
    'name': 'descriptive_name', # What this migration does
    'sql': 'ALTER TABLE...',   # SQL to execute
    'check': 'SELECT...'       # SQL to check if already applied
}
```

### Testing Migrations

```bash
# Test migrations manually
python3 /opt/field_trainer/db_migrations.py

# Check current schema version
python3 << EOF
from field_trainer.db_migrations import get_schema_version
print(f"Schema version: {get_schema_version('/opt/data/field_trainer.db')}")
EOF
```

### Viewing Applied Migrations

```bash
sqlite3 /opt/data/field_trainer.db "SELECT * FROM schema_migrations"
```

---

## Pre-Commit Checklist

Before committing code that touches the database:

- [ ] Did I add a new column/table?
- [ ] Did I create a migration for it?
- [ ] Did I test with a fresh database?
- [ ] Does the migration run successfully?
- [ ] Did I commit the migration file?

---

## Quick Commands

```bash
# Check schema version
python3 /opt/field_trainer/db_migrations.py

# Force re-run migrations (for testing)
sqlite3 /opt/data/field_trainer.db "DELETE FROM schema_migrations WHERE version = 3"
sudo pkill -f field_trainer_main.py
python3 field_trainer_main.py --host 0.0.0.0 --port 5000 --debug 0

# Backup database before testing
cp /opt/data/field_trainer.db /opt/data/field_trainer.db.backup

# Restore database if something breaks
cp /opt/data/field_trainer.db.backup /opt/data/field_trainer.db
```

---

## Common Scenarios

### Scenario 1: Adding a Column to Existing Table

**Migration:**
```python
{
    'version': 4,
    'name': 'add_notes_to_courses',
    'sql': 'ALTER TABLE courses ADD COLUMN notes TEXT',
    'check': "SELECT COUNT(*) FROM pragma_table_info('courses') WHERE name='notes'"
}
```

### Scenario 2: Creating a New Table

**Migration:**
```python
{
    'version': 5,
    'name': 'create_training_logs',
    'sql': '''
        CREATE TABLE IF NOT EXISTS training_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'check': "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='training_logs'"
}
```

### Scenario 3: Modifying Column (Requires Recreation)

SQLite doesn't support ALTER COLUMN, so you need to recreate:

```python
{
    'version': 6,
    'name': 'change_status_column',
    'sql': '''
        -- Create new table with updated schema
        CREATE TABLE sessions_new AS SELECT * FROM sessions;
        DROP TABLE sessions;
        ALTER TABLE sessions_new RENAME TO sessions;
        -- Add new constraint/column here
    ''',
    'check': "SELECT 1"  # Custom check needed
}
```

---

## Emergency: Fix Broken Schema

If you're in a state where schema is broken:

```bash
# 1. Check what's wrong
sqlite3 /opt/data/field_trainer.db ".schema sessions"

# 2. Add missing column manually (temporary fix)
sqlite3 /opt/data/field_trainer.db "ALTER TABLE sessions ADD COLUMN pattern_config TEXT"

# 3. Create proper migration so it doesn't happen again
# Edit db_migrations.py and add the migration

# 4. Test migration on fresh database
rm /opt/data/field_trainer.db
python3 field_trainer_main.py --host 0.0.0.0 --port 5000 --debug 0
```

---

## Summary

**Golden Rule:** Never manually ALTER TABLE without creating a migration!

**Two Options:**
1. **Migration System** (Recommended) - Add to `db_migrations.py`, automatic on startup
2. **CREATE TABLE Update** (Simple) - Update db_manager.py, delete database, restart

**Choose Migration System if:**
- You have production data you can't lose
- Multiple developers working on codebase
- Deploying to multiple environments

**Choose CREATE TABLE Update if:**
- Solo developer
- Small project
- OK deleting database during development

---

**Current Status:**
- ✅ Migration system installed
- ✅ Runs automatically on server startup
- ✅ Migrations 1-2 already applied (pattern_config, timer_start_at)

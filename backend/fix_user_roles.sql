-- Fix legacy users without a role assigned
-- PostgreSQL + SQLite compatible
-- Run this against your database to assign LAWYER role to users with NULL roles

-- Check how many users need fixing
SELECT COUNT(*) as users_with_null_role
FROM users
WHERE
    role IS NULL;

-- View affected users before update
SELECT id, email, role FROM users WHERE role IS NULL;

-- Fix: Assign LAWYER role to all users with NULL role
UPDATE users SET role = 'lawyer' WHERE role IS NULL;

-- Verify the fix
SELECT id, email, role FROM users WHERE role IS NULL;
-- Should be empty now
SELECT COUNT(*) as total_users FROM users;

SELECT role, COUNT(*) as count
FROM users
GROUP BY
    role
ORDER BY role;
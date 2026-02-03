# Philm SQL Cheatsheet

## The Basics

```sql
-- SELECT = what columns you want
-- FROM = which table
-- WHERE = filter rows
-- ORDER BY = sort results
-- LIMIT = max rows returned
-- JOIN = connect tables together
```

## Your Tables

| Table | What's in it |
|-------|--------------|
| `videos` | All scanned videos (id, filename, path, tier) |
| `gaze_moments` | Mulvey gaze analysis |
| `sublime_moments` | Sublime classification |
| `affect_moments` | Massumi affect intensity |
| `camera_moments` | Camera kinetics |
| `hauntology_moments` | Fisher/Han/Curtis analysis |
| `baudrillard_moments` | Simulacra/hyperreality |
| `barthes_moments` | Punctum/studium/mythology |
| `benjamin_moments` | Aura/dialectical image |
| `zizek_moments` | Parallax/Lacanian registers |
| `epistemic_moments` | Truth claims/evidence |
| `foucault_moments` | Power/surveillance |
| `virilio_moments` | Speed/accident |
| `video_fts` | Full-text search index |

---

## Essential Queries

### 1. See all videos
```sql
SELECT id, filename, tier FROM videos ORDER BY id DESC;
```

### 2. See a specific table's contents
```sql
SELECT * FROM hauntology_moments LIMIT 20;
```

### 3. Connect analysis to video filename (JOIN)
```sql
SELECT v.filename, h.smoothness, h.description
FROM hauntology_moments h
JOIN videos v ON h.video_id = v.id;
```

### 4. Filter with WHERE
```sql
SELECT v.filename, h.description
FROM hauntology_moments h
JOIN videos v ON h.video_id = v.id
WHERE h.smoothness = 'smooth_evil';
```

### 5. Full-text search (searches ALL descriptions)
```sql
SELECT * FROM video_fts WHERE video_fts MATCH 'tank';
SELECT * FROM video_fts WHERE video_fts MATCH 'gaze';
SELECT * FROM video_fts WHERE video_fts MATCH 'sublime';
```

---

## Analysis-Specific Queries

### Hauntology (Fisher/Han/Curtis)
```sql
-- All hauntology analyses with video names
SELECT v.filename, h.temporal_pathology, h.smoothness,
       h.capitalist_realism, h.hypernormal, h.description
FROM hauntology_moments h
JOIN videos v ON h.video_id = v.id;

-- Find "smooth evil" moments
SELECT v.filename, h.description
FROM hauntology_moments h
JOIN videos v ON h.video_id = v.id
WHERE h.smoothness = 'smooth_evil';

-- Find cancelled futures
SELECT v.filename, h.lost_future, h.description
FROM hauntology_moments h
JOIN videos v ON h.video_id = v.id
WHERE h.temporal_pathology = 'cancelled_future';
```

### Gaze (Mulvey)
```sql
-- All gaze analyses
SELECT v.filename, g.gaze_type, g.gender_presentation,
       g.fourth_wall_break, g.description
FROM gaze_moments g
JOIN videos v ON g.video_id = v.id;

-- Find fourth wall breaks
SELECT v.filename, g.timecode, g.description
FROM gaze_moments g
JOIN videos v ON g.video_id = v.id
WHERE g.fourth_wall_break = 1;

-- Count by gaze type
SELECT gaze_type, COUNT(*) as count
FROM gaze_moments
GROUP BY gaze_type
ORDER BY count DESC;
```

### Sublime
```sql
-- All sublime moments
SELECT v.filename, s.sublime_type, s.recovery, s.description
FROM sublime_moments s
JOIN videos v ON s.video_id = v.id;

-- Find moments with no recovery
SELECT v.filename, s.sublime_type, s.description
FROM sublime_moments s
JOIN videos v ON s.video_id = v.id
WHERE s.recovery = 0;
```

### Barthes (Punctum/Studium)
```sql
-- Find the punctum (the wound, the prick)
SELECT v.filename, b.punctum_description, b.death_present
FROM barthes_moments b
JOIN videos v ON b.video_id = v.id
WHERE b.punctum_present = 1;

-- Mythology operations
SELECT v.filename, b.register, b.myth_operation, b.description
FROM barthes_moments b
JOIN videos v ON b.video_id = v.id;
```

### Zizek (Parallax/Lacan)
```sql
-- Track Lacanian registers
SELECT v.filename, z.register, z.parallax_type, z.description
FROM zizek_moments z
JOIN videos v ON z.video_id = v.id;

-- Find traversals of fantasy
SELECT v.filename, z.description
FROM zizek_moments z
JOIN videos v ON z.video_id = v.id
WHERE z.traversal_moment = 1;
```

### Benjamin (Aura/Dialectical Image)
```sql
-- Aura status
SELECT v.filename, b.aura_status, b.dialectical_image, b.description
FROM benjamin_moments b
JOIN videos v ON b.video_id = v.id;

-- Optical unconscious moments
SELECT v.filename, b.description
FROM benjamin_moments b
JOIN videos v ON b.video_id = v.id
WHERE b.optical_unconscious = 1;
```

### Baudrillard (Simulacra)
```sql
-- Simulacra orders
SELECT v.filename, b.simulacra_order, b.precession, b.description
FROM baudrillard_moments b
JOIN videos v ON b.video_id = v.id;

-- Find hyperreal moments (precession of simulacra)
SELECT v.filename, b.description
FROM baudrillard_moments b
JOIN videos v ON b.video_id = v.id
WHERE b.precession = 1;
```

---

## Counting & Aggregating

```sql
-- Count videos by tier
SELECT tier, COUNT(*) as count FROM videos GROUP BY tier;

-- Count analyses per mode
SELECT 'hauntology' as mode, COUNT(*) FROM hauntology_moments
UNION SELECT 'gaze', COUNT(*) FROM gaze_moments
UNION SELECT 'sublime', COUNT(*) FROM sublime_moments
UNION SELECT 'affect', COUNT(*) FROM affect_moments
UNION SELECT 'barthes', COUNT(*) FROM barthes_moments
UNION SELECT 'zizek', COUNT(*) FROM zizek_moments
UNION SELECT 'benjamin', COUNT(*) FROM benjamin_moments
UNION SELECT 'baudrillard', COUNT(*) FROM baudrillard_moments;

-- Distribution of a category
SELECT smoothness, COUNT(*) as count
FROM hauntology_moments
GROUP BY smoothness
ORDER BY count DESC;
```

---

## Combining Analyses (Advanced)

```sql
-- Videos with BOTH hauntology AND barthes analysis
SELECT DISTINCT v.filename
FROM videos v
JOIN hauntology_moments h ON h.video_id = v.id
JOIN barthes_moments b ON b.video_id = v.id;

-- Find smooth_evil moments that also have punctum
SELECT v.filename, h.smoothness, b.punctum_description
FROM videos v
JOIN hauntology_moments h ON h.video_id = v.id
JOIN barthes_moments b ON b.video_id = v.id
WHERE h.smoothness = 'smooth_evil' AND b.punctum_present = 1;
```

---

## Quick Reference

| Want to... | Use... |
|------------|--------|
| See everything | `SELECT * FROM table_name` |
| Pick columns | `SELECT col1, col2 FROM table` |
| Filter rows | `WHERE column = 'value'` |
| Sort | `ORDER BY column DESC` |
| Limit results | `LIMIT 10` |
| Connect tables | `JOIN table2 ON table1.id = table2.foreign_id` |
| Count things | `SELECT COUNT(*) FROM table` |
| Group & count | `GROUP BY column` |
| Search text | `WHERE column LIKE '%word%'` |
| Full-text search | `SELECT * FROM video_fts WHERE video_fts MATCH 'word'` |

---

## Keyboard Shortcuts (DB Browser)

- **Cmd+Enter** - Run query
- **Cmd+/** - Comment/uncomment line
- **Cmd+S** - Save database

---

*Generated for Philm archive v0.3.0*

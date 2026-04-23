# MindHive — Campus Q&A Platform

A full-stack campus knowledge-sharing platform built with:
- **Backend**: Python (stdlib `http.server`) + SQLite — mirrors Django/SQLite architecture
- **Frontend**: Bootstrap 5 + jQuery (exactly as stated in resume)
- **REST API**: Clean JSON endpoints for all operations

## Run It

```bash
python3 app.py
```

Then open **http://localhost:8000** in your browser.

No dependencies to install — uses Python's built-in HTTP server and SQLite.

## Demo Login
- **Username**: `idc` / **Password**: `pass123`
- Other demo users: `priya_iitkgp`, `rohan_cs`, `neha_mse`, `vikram_ee` (same password)

## Features
- ✅ User registration & login (session-based auth, SHA-256 password hashing)
- ✅ Ask questions with tags
- ✅ Threaded comments / replies
- ✅ Upvote / downvote posts and comments
- ✅ Search questions (title + body)
- ✅ Filter by tag
- ✅ Sort: Newest / Most Voted / Most Viewed
- ✅ Pagination (10 posts/page)
- ✅ View counter on posts
- ✅ Seeded with realistic campus Q&A data

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/register` | Create account |
| POST | `/api/login` | Sign in |
| POST | `/api/logout` | Sign out |
| GET | `/api/me` | Current user |
| GET | `/api/posts` | List posts (search, tag, sort, page) |
| POST | `/api/posts` | Create post |
| GET | `/api/posts/:id` | Get post + threaded comments |
| POST | `/api/posts/:id/comments` | Add comment/reply |
| POST | `/api/vote` | Vote on post or comment |
| GET | `/api/tags` | List all tags with counts |
| GET | `/api/stats` | Community statistics |

## Tech Stack 
- **Backend**: Python stdlib HTTP server (equivalent to Django's dev server), SQLite
- **Frontend**: Bootstrap 5, jQuery 3.7
- **Database schema**: Users, Posts, Tags, PostTags (many-to-many), Comments (self-referential for threading), Votes


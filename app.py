#!/usr/bin/env python3
"""MindHive - Run: python app.py  then open http://localhost:8000"""

import json, sqlite3, hashlib, os, random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB = "mindhive.db"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def hpw(p): return hashlib.sha256(p.encode()).hexdigest()

def setup():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, color TEXT, created_at TEXT DEFAULT(datetime('now')));
        CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, user_id INTEGER, views INTEGER DEFAULT 0, created_at TEXT DEFAULT(datetime('now')));
        CREATE TABLE IF NOT EXISTS tags(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS post_tags(post_id INTEGER, tag_id INTEGER, PRIMARY KEY(post_id,tag_id));
        CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT, post_id INTEGER, user_id INTEGER, parent_id INTEGER, created_at TEXT DEFAULT(datetime('now')));
        CREATE TABLE IF NOT EXISTS votes(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, post_id INTEGER, comment_id INTEGER, value INTEGER, UNIQUE(user_id,post_id), UNIQUE(user_id,comment_id));
    """)
    c.commit()
    if c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"] == 0:
        seed(c)
    c.close()

def seed(c):
    colors=["#7C6AF0","#FF6B8A","#43D9B8","#F7931E","#00B4D8"]
    users=[("anchit","pass123"),("priya_iitkgp","pass123"),("rohan_cs","pass123"),("neha_mse","pass123"),("vikram_ee","pass123")]
    for i,(u,p) in enumerate(users):
        c.execute("INSERT INTO users(username,password_hash,color) VALUES(?,?,?)",(u,hpw(p),colors[i]))
    for t in ["DSA","Machine Learning","Web Dev","Placements","Research","Python","C++","GATE","Internships","System Design"]:
        c.execute("INSERT INTO tags(name) VALUES(?)",(t,))
    posts=[
        (1,"How do I prepare for FAANG interviews from IIT?","I'm a 3rd year at IIT Kanpur. Where do I start for FAANG prep? Heard about Striver's sheet. Any full roadmap?",["DSA","Placements"]),
        (2,"Best way to learn ML from scratch as an MSE student?","My branch is Materials Science but I love ML. Have decent Python. Andrew Ng or fast.ai? How important is linear algebra?",["Machine Learning","Python"]),
        (3,"Django vs Flask for a 48hr hackathon?","Team of 3, 48hrs. Need REST APIs + simple frontend. Django too heavy? Flask too barebones?",["Web Dev","Python"]),
        (4,"Tips for GATE 2025 while doing a summer internship?","2 month internship this summer and want to prep for GATE too. Feasible? How many hours/day?",["GATE","Internships"]),
        (5,"Graph Neural Networks for fraud detection - resources?","Working on AML project, need GNNs. PyTorch Geometric or DGL? Good papers to start?",["Machine Learning","Research"]),
    ]
    for uid,title,body,ptags in posts:
        c.execute("INSERT INTO posts(title,body,user_id) VALUES(?,?,?)",(title,body,uid))
        pid=c.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        for tn in ptags:
            tid=c.execute("SELECT id FROM tags WHERE name=?",(tn,)).fetchone()["id"]
            c.execute("INSERT INTO post_tags VALUES(?,?)",(pid,tid))
    comments=[
        (1,2,None,"Striver's sheet is the best start! I did 150 problems before placements and cracked Amazon. Consistency beats intensity."),
        (1,3,None,"NeetCode on YouTube is excellent. Understand time complexity deeply before grinding."),
        (1,4,1,"Agreed — also do mock interviews on Pramp once you hit 100+ problems."),
        (2,1,None,"Andrew Ng for theory (3-4 weeks), then fast.ai for hands-on. Do both."),
        (2,5,None,"Linear algebra is crucial. Gilbert Strang MIT OCW lectures are gold."),
        (3,4,None,"Flask + SQLAlchemy for hackathons. REST API running in 20 mins."),
        (3,1,None,"If your team knows Django, the admin panel saves huge time. Depends on familiarity."),
        (4,2,None,"Cap internship at 8hrs, use evenings for GATE. Full weekends = GATE only. Engineering Maths first!"),
        (5,3,None,"PyG for research, DGL for production. For 1M nodes use GraphSAGE mini-batch."),
        (5,1,None,"Check the Amazon fraud detection GNN paper. Kipf & Welling GCN is essential reading."),
    ]
    for pid,uid,par,body in comments:
        c.execute("INSERT INTO comments(body,post_id,user_id,parent_id) VALUES(?,?,?,?)",(body,pid,uid,par))
    c.commit()

def session_user(handler):
    for part in handler.headers.get("Cookie","").split(";"):
        part=part.strip()
        if part.startswith("uid="):
            uid=part[4:]
            c=db(); row=c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); c.close()
            return dict(row) if row else None
    return None

def jsend(h,data,code=200):
    b=json.dumps(data).encode()
    h.send_response(code); h.send_header("Content-Type","application/json"); h.send_header("Content-Length",len(b))
    if hasattr(h,"_cookie"): h.send_header("Set-Cookie",h._cookie)
    h.end_headers(); h.wfile.write(b)

def hsend(h,html,code=200):
    b=html.encode()
    h.send_response(code); h.send_header("Content-Type","text/html; charset=utf-8"); h.send_header("Content-Length",len(b))
    if hasattr(h,"_cookie"): h.send_header("Set-Cookie",h._cookie)
    h.end_headers(); h.wfile.write(b)

def ptags(c,pid):
    return [r["name"] for r in c.execute("SELECT t.name FROM tags t JOIN post_tags pt ON pt.tag_id=t.id WHERE pt.post_id=?",(pid,)).fetchall()]

def pscore(c,pid):
    return c.execute("SELECT COALESCE(SUM(value),0) as s FROM votes WHERE post_id=?",(pid,)).fetchone()["s"]

def cscore(c,cid):
    return c.execute("SELECT COALESCE(SUM(value),0) as s FROM votes WHERE comment_id=?",(cid,)).fetchone()["s"]

def pcomments(c,pid):
    rows=c.execute("SELECT cm.*,u.username,u.color FROM comments cm JOIN users u ON u.id=cm.user_id WHERE cm.post_id=? ORDER BY cm.created_at",(pid,)).fetchall()
    def thread(par=None):
        res=[]
        for r in rows:
            if r["parent_id"]==par:
                c2=db(); sc=cscore(c2,r["id"]); c2.close()
                res.append({"id":r["id"],"body":r["body"],"username":r["username"],"color":r["color"],"created_at":r["created_at"],"score":sc,"replies":thread(r["id"])})
        return res
    return thread()

PAGE="""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MindHive</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
<style>
:root{--bg:#0D0F14;--sf:#13161E;--sf2:#1A1E29;--br:#252836;--ac:#7C6AF0;--ac2:#FF6B8A;--ac3:#43D9B8;--tx:#E8EAF0;--mu:#6B7280;}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:var(--bg);color:var(--tx);font-family:'DM Sans',sans-serif;font-size:15px;line-height:1.6;min-height:100vh;}
a{text-decoration:none;}
.nav{background:rgba(13,15,20,.94);backdrop-filter:blur(16px);border-bottom:1px solid var(--br);padding:12px 0;position:sticky;top:0;z-index:100;}
.brand{font-family:'Playfair Display',serif;font-size:1.55rem;font-weight:900;background:linear-gradient(135deg,var(--ac),var(--ac2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;cursor:pointer;}
.brand span{-webkit-text-fill-color:var(--ac3);}
.nbtn{background:transparent;border:1.5px solid var(--br);color:var(--tx);padding:6px 18px;border-radius:8px;font-size:.85rem;font-weight:500;cursor:pointer;transition:all .2s;}
.nbtn:hover{border-color:var(--ac);color:var(--ac);}
.nbtn.p{background:var(--ac);border-color:var(--ac);color:#fff;}
.nbtn.p:hover{opacity:.85;}
.layout{max-width:1180px;margin:0 auto;padding:28px 20px;display:grid;grid-template-columns:1fr 290px;gap:24px;}
@media(max-width:768px){.layout{grid-template-columns:1fr;}.side{display:none;}}
.hero{background:linear-gradient(135deg,rgba(124,106,240,.13),rgba(255,107,138,.08));border:1px solid var(--br);border-radius:12px;padding:28px;margin-bottom:22px;}
.hero h1{font-family:'Playfair Display',serif;font-size:2rem;font-weight:900;margin-bottom:6px;}
.hero p{color:var(--mu);max-width:480px;}
.card{background:var(--sf);border:1px solid var(--br);border-radius:12px;padding:18px 20px;margin-bottom:12px;cursor:pointer;transition:border-color .2s,transform .15s;}
.card:hover{border-color:var(--ac);transform:translateY(-2px);}
.ptitle{font-size:1rem;font-weight:600;margin-bottom:7px;}
.pbody{color:var(--mu);font-size:.87rem;margin-bottom:10px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.meta{display:flex;align-items:center;gap:14px;font-size:.79rem;color:var(--mu);flex-wrap:wrap;}
.av{width:22px;height:22px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:.58rem;font-weight:700;color:#fff;flex-shrink:0;}
.tag{background:var(--sf2);border:1px solid var(--br);color:var(--ac);padding:2px 10px;border-radius:20px;font-size:.74rem;font-weight:500;cursor:pointer;transition:all .15s;display:inline-block;}
.tag:hover,.tag.on{background:var(--ac);color:#fff;border-color:var(--ac);}
.tb{display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;align-items:center;}
.srch{flex:1;min-width:180px;background:var(--sf);border:1.5px solid var(--br);border-radius:10px;padding:9px 15px;color:var(--tx);font-size:.9rem;outline:none;}
.srch:focus{border-color:var(--ac);}
.srch::placeholder{color:var(--mu);}
.srt{background:var(--sf);border:1.5px solid var(--br);border-radius:10px;color:var(--tx);padding:9px 12px;font-size:.87rem;outline:none;cursor:pointer;}
.fab{background:linear-gradient(135deg,var(--ac),var(--ac2));border:none;border-radius:10px;color:#fff;padding:10px 20px;font-size:.87rem;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:5px;white-space:nowrap;transition:opacity .2s;}
.fab:hover{opacity:.85;}
.pgbar{display:flex;gap:6px;justify-content:center;margin-top:20px;}
.pgbtn{background:var(--sf);border:1px solid var(--br);color:var(--tx);width:36px;height:36px;border-radius:8px;font-size:.84rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;}
.pgbtn:hover,.pgbtn.on{background:var(--ac);border-color:var(--ac);color:#fff;}
/* MODAL */
.ov{position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:9000;display:none;align-items:center;justify-content:center;padding:16px;}
.ov.open{display:flex;}
.mbox{background:var(--sf);border:1px solid var(--br);border-radius:16px;padding:30px;width:100%;max-width:480px;max-height:90vh;overflow-y:auto;position:relative;z-index:9001;}
.mtitle{font-family:'Playfair Display',serif;font-size:1.45rem;font-weight:700;margin-bottom:22px;}
.lbl{display:block;font-size:.8rem;font-weight:600;color:var(--mu);letter-spacing:.8px;text-transform:uppercase;margin-bottom:5px;}
.inp{width:100%;background:var(--sf2) !important;border:1.5px solid var(--br) !important;border-radius:10px !important;padding:10px 14px !important;color:var(--tx) !important;font-size:.92rem !important;outline:none !important;margin-bottom:14px !important;display:block !important;box-sizing:border-box !important;font-family:'DM Sans',sans-serif !important;-webkit-text-fill-color:var(--tx) !important;}
.inp:focus{border-color:var(--ac) !important;}
textarea.inp{resize:vertical;min-height:90px;}
.sbtn{width:100%;background:var(--ac);border:none;border-radius:10px;color:#fff;padding:11px;font-size:.94rem;font-weight:600;cursor:pointer;transition:opacity .2s;font-family:'DM Sans',sans-serif;}
.sbtn:hover{opacity:.85;}
.err{color:var(--ac2);font-size:.84rem;margin-bottom:10px;}
.xbtn{position:absolute;top:16px;right:18px;background:none;border:none;color:var(--mu);font-size:1.5rem;cursor:pointer;line-height:1;z-index:9002;}
.xbtn:hover{color:var(--tx);}
/* SIDEBAR */
.sc{background:var(--sf);border:1px solid var(--br);border-radius:12px;padding:18px;margin-bottom:18px;}
.stitle{font-size:.73rem;font-weight:600;letter-spacing:1.4px;text-transform:uppercase;color:var(--mu);margin-bottom:12px;}
.sstat{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--br);font-size:.84rem;}
.sstat:last-child{border-bottom:none;}
/* POST DETAIL */
.dh{background:var(--sf);border:1px solid var(--br);border-radius:12px;padding:26px;margin-bottom:18px;}
.dtitle{font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;line-height:1.3;margin-bottom:14px;}
.dbody{color:#B0B8C8;line-height:1.75;font-size:.94rem;margin-bottom:18px;white-space:pre-wrap;}
.vbtn{background:var(--sf2);border:1px solid var(--br);color:var(--mu);padding:5px 12px;border-radius:8px;font-size:.81rem;cursor:pointer;transition:all .15s;}
.vbtn:hover{background:var(--ac);color:#fff;border-color:var(--ac);}
.ci{background:var(--sf);border:1px solid var(--br);border-radius:10px;padding:13px 15px;margin-bottom:9px;}
.ci.rep{margin-left:26px;border-left:3px solid var(--ac);border-radius:0 10px 10px 0;}
.cmeta{font-size:.77rem;color:var(--mu);margin-bottom:5px;}
.cbody{font-size:.89rem;color:#C4CAD8;line-height:1.6;}
.rl{color:var(--mu);font-size:.77rem;cursor:pointer;margin-top:5px;display:inline-block;}
.rl:hover{color:var(--ac);}
.rform{display:none;margin-top:9px;}
.bk{background:none;border:none;color:var(--mu);cursor:pointer;font-size:.87rem;display:flex;align-items:center;gap:5px;padding:0;margin-bottom:18px;}
.bk:hover{color:var(--tx);}
.upill{background:var(--sf2);border:1px solid var(--br);border-radius:20px;padding:5px 13px;font-size:.81rem;display:flex;align-items:center;gap:7px;}
/* TOAST */
#tc{position:fixed;bottom:22px;right:22px;z-index:9999;display:flex;flex-direction:column;gap:7px;}
.ti{background:var(--sf2);border:1px solid var(--br);border-radius:10px;padding:11px 18px;font-size:.87rem;max-width:280px;}
.ti.ok{border-left:3px solid var(--ac3);}
.ti.er{border-left:3px solid var(--ac2);}
.skel{background:linear-gradient(90deg,var(--sf) 25%,var(--sf2) 50%,var(--sf) 75%);background-size:200% 100%;animation:sh 1.5s infinite;border-radius:8px;height:90px;margin-bottom:12px;}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
.demo-guide{border-color:rgba(124,106,240,.4) !important;background:rgba(124,106,240,.06) !important;}
</style>
</head>
<body>
<nav class="nav">
  <div style="max-width:1180px;margin:0 auto;padding:0 20px;display:flex;align-items:center;justify-content:space-between;gap:12px;">
    <div class="brand" onclick="showFeed()">Mind<span>Hive</span></div>
    <div style="display:flex;align-items:center;gap:9px;">
      <div id="ng" style="display:flex;gap:8px;">
        <button class="nbtn" onclick="openM('lm')">Sign In</button>
        <button class="nbtn p" onclick="openM('rm')">Join Free</button>
      </div>
      <div id="nu" style="display:none;gap:9px;align-items:center;" class="d-flex">
        <div class="upill" id="ud"></div>
        <button class="nbtn" onclick="logout()">Sign Out</button>
      </div>
    </div>
  </div>
</nav>

<div class="layout">
  <main>
    <div id="fv">
      <div class="hero">
        <h1>Ask. Answer. Grow.</h1>
        <p>The campus knowledge network for IIT students — share expertise, solve problems, build together.</p>
      </div>
      <div class="tb">
        <input class="srch" type="text" id="si" placeholder="Search questions..." oninput="dsearch()">
        <select class="srt" id="ss" onchange="loadP()">
          <option value="newest">Newest</option>
          <option value="popular">Most Voted</option>
          <option value="views">Most Viewed</option>
          <option value="oldest">Oldest</option>
        </select>
        <button class="fab" onclick="newPost()"><i class="bi bi-plus-lg"></i> Ask Question</button>
      </div>
      <div id="atb" style="margin-bottom:12px;display:none;">
        <span style="font-size:.82rem;color:var(--mu);">Tag: </span>
        <span class="tag on" id="atl"></span>
        <button onclick="clrTag()" style="background:none;border:none;color:var(--mu);cursor:pointer;font-size:.82rem;margin-left:8px;">✕ Clear</button>
      </div>
      <div id="pc"></div>
      <div id="pb" class="pgbar"></div>
    </div>
    <div id="dv" style="display:none;">
      <button class="bk" onclick="showFeed()"><i class="bi bi-arrow-left"></i> Back</button>
      <div id="dc"></div>
    </div>
  </main>
  <aside class="side">
    <div class="sc demo-guide">
      <div class="stitle" style="color:var(--ac);">🎯 Live Demo Steps</div>
      <div style="font-size:.81rem;color:var(--mu);line-height:1.9;">
        <div>1️⃣ <a href="#" onclick="openM('rm');return false;" style="color:var(--ac);">Create new account</a></div>
        <div>2️⃣ <a href="#" onclick="newPost();return false;" style="color:var(--ac);">Post a question</a></div>
        <div>3️⃣ Click any question → answer it</div>
        <div>4️⃣ Upvote posts or answers</div>
        <div>5️⃣ Search / filter by tag</div>
        <div style="margin-top:9px;padding-top:9px;border-top:1px solid var(--br);font-size:.77rem;">
          Demo login: <code style="color:var(--ac3);">anchit / pass123</code>
        </div>
      </div>
    </div>
    <div class="sc">
      <div class="stitle">Popular Tags</div>
      <div style="display:flex;flex-wrap:wrap;gap:7px;" id="tc2"></div>
    </div>
    <div class="sc">
      <div class="stitle">Community Stats</div>
      <div class="sstat"><span>Questions</span><strong id="sp" style="color:var(--ac);font-family:'JetBrains Mono'">—</strong></div>
      <div class="sstat"><span>Members</span><strong id="su" style="color:var(--ac);font-family:'JetBrains Mono'">—</strong></div>
      <div class="sstat"><span>Answers</span><strong id="sc2" style="color:var(--ac);font-family:'JetBrains Mono'">—</strong></div>
      <div class="sstat"><span>Tags</span><strong id="st" style="color:var(--ac);font-family:'JetBrains Mono'">—</strong></div>
    </div>
  </aside>
</div>

<!-- LOGIN MODAL -->
<div class="ov" id="lm" onclick="bgClose(event,'lm')">
  <div class="mbox">
    <button class="xbtn" onclick="closeM('lm')">×</button>
    <div class="mtitle">Welcome back</div>
    <div class="err" id="le" style="display:none;"></div>
    <label class="lbl">Username</label>
    <input class="inp" type="text" id="lu" placeholder="your_username" autocomplete="username">
    <label class="lbl">Password</label>
    <input class="inp" type="password" id="lp" placeholder="your password" autocomplete="current-password">
    <button class="sbtn" onclick="doLogin()">Sign In</button>
    <p style="text-align:center;margin-top:14px;font-size:.84rem;color:var(--mu);">
      No account? <a href="#" onclick="switchM('lm','rm')" style="color:var(--ac);">Join MindHive</a>
    </p>
    <p style="text-align:center;margin-top:6px;font-size:.77rem;color:var(--mu);">
      Try: <code style="color:var(--ac3);">anchit</code> / <code style="color:var(--ac3);">pass123</code>
    </p>
  </div>
</div>

<!-- REGISTER MODAL -->
<div class="ov" id="rm" onclick="bgClose(event,'rm')">
  <div class="mbox">
    <button class="xbtn" onclick="closeM('rm')">×</button>
    <div class="mtitle">Join MindHive</div>
    <div class="err" id="re" style="display:none;"></div>
    <label class="lbl">Username</label>
    <input class="inp" type="text" id="ru" placeholder="choose_username" autocomplete="username">
    <label class="lbl">Password</label>
    <input class="inp" type="password" id="rp" placeholder="choose password" autocomplete="new-password">
    <button class="sbtn" onclick="doReg()">Create Account</button>
    <p style="text-align:center;margin-top:14px;font-size:.84rem;color:var(--mu);">
      Have an account? <a href="#" onclick="switchM('rm','lm')" style="color:var(--ac);">Sign in</a>
    </p>
  </div>
</div>

<!-- NEW POST MODAL -->
<div class="ov" id="pm" onclick="bgClose(event,'pm')">
  <div class="mbox">
    <button class="xbtn" onclick="closeM('pm')">×</button>
    <div class="mtitle">Ask a Question</div>
    <div class="err" id="pe" style="display:none;"></div>
    <label class="lbl">Question Title</label>
    <input class="inp" type="text" id="pt" placeholder="What's your question?">
    <label class="lbl">Details</label>
    <textarea class="inp" id="pb2" placeholder="Add context, what you've tried..." rows="5"></textarea>
    <label class="lbl">Tags (comma separated)</label>
    <input class="inp" type="text" id="ptg" placeholder="e.g. DSA, Python, ML">
    <button class="sbtn" onclick="doPost()">Post Question</button>
  </div>
</div>

<div id="tc"></div>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script>
let me=null, pg=1, ctag='', stimer=null, curPid=null;

$(function(){
  checkMe(); loadP(); loadTags(); loadStats();
  $('#lp,#rp').on('keydown',function(e){ if(e.key==='Enter') e.currentTarget.id==='lp'?doLogin():doReg(); });
});

function checkMe(){
  $.get('/api/me',function(d){
    if(d.user){me=d.user;showUser();}else{me=null;hideUser();}
  });
}
function showUser(){
  $('#ng').hide();
  $('#ud').html(`<div class="av" style="background:${me.color}">${me.username[0].toUpperCase()}</div><span>${me.username}</span>`);
  $('#nu').show();
}
function hideUser(){ $('#nu').hide(); $('#ng').show(); }
function logout(){
  $.post('/api/logout',function(){ me=null; hideUser(); showFeed(); toast('Signed out'); });
}

function loadP(p){
  if(p) pg=p;
  const q=$('#si').val().trim(), s=$('#ss').val();
  let url=`/api/posts?page=${pg}&sort=${s}`;
  if(q) url+='&q='+encodeURIComponent(q);
  if(ctag) url+='&tag='+encodeURIComponent(ctag);
  $('#pc').html('<div class="skel"></div><div class="skel" style="height:70px;opacity:.6"></div>');
  $.get(url,function(d){ renderPosts(d.posts); renderPg(d.page,d.pages); });
}

function renderPosts(ps){
  if(!ps.length){$('#pc').html('<div style="text-align:center;padding:50px;color:var(--mu)"><div style="font-size:2.5rem">🐝</div><div style="margin-top:8px;font-size:1rem;font-weight:600;color:var(--tx)">No questions yet</div><div>Be the first to ask!</div></div>');return;}
  $('#pc').html(ps.map(p=>`
    <div class="card" onclick="openPost(${p.id})">
      <div class="ptitle">${esc(p.title)}</div>
      <div class="pbody">${esc(p.body)}</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:9px">${p.tags.map(t=>`<span class="tag" onclick="ftag('${t}',event)">${t}</span>`).join('')}</div>
      <div class="meta">
        <div style="display:flex;align-items:center;gap:5px"><div class="av" style="background:${p.color}">${p.username[0].toUpperCase()}</div><span>${esc(p.username)}</span></div>
        <span style="color:var(--ac3)">▲ ${p.score}</span>
        <span>💬 ${p.comments}</span>
        <span>👁 ${p.views}</span>
        <span style="margin-left:auto">${fmtTime(p.created_at)}</span>
      </div>
    </div>`).join(''));
}

function renderPg(p,pages){
  if(pages<=1){$('#pb').empty();return;}
  $('#pb').html(Array.from({length:pages},(_,i)=>`<button class="pgbtn ${i+1===p?'on':''}" onclick="loadP(${i+1})">${i+1}</button>`).join(''));
}

function openPost(id){
  curPid=id;
  $('#fv').hide(); $('#dv').show();
  $('#dc').html('<div class="skel" style="height:180px"></div>');
  $.get('/api/posts/'+id,function(d){ renderDetail(d.post,d.comments); });
}

function renderDetail(p,comments){
  const tags=p.tags.map(t=>`<span class="tag">${t}</span>`).join(' ');
  const nc=countC(comments);
  $('#dc').html(`
    <div class="dh">
      <div class="dtitle">${esc(p.title)}</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px">${tags}</div>
      <div class="dbody">${esc(p.body)}</div>
      <hr style="border-color:var(--br);margin:16px 0">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px">
        <div style="display:flex;align-items:center;gap:9px">
          <div class="av" style="background:${p.color};width:30px;height:30px;font-size:.73rem">${p.username[0].toUpperCase()}</div>
          <div><div style="font-weight:600;font-size:.89rem">${esc(p.username)}</div><div style="color:var(--mu);font-size:.77rem">${fmtTime(p.created_at)} · ${p.views} views</div></div>
        </div>
        <div style="display:flex;align-items:center;gap:7px">
          <button class="vbtn" onclick="vote('post',${p.id},1)">▲ Upvote</button>
          <span style="font-weight:700;color:var(--ac3)">${p.score}</span>
          <button class="vbtn" onclick="vote('post',${p.id},-1)">▼</button>
        </div>
      </div>
    </div>
    <div style="font-weight:600;margin-bottom:14px" data-ac>${nc} Answer${nc!==1?'s':''}</div>
    <div id="cs">${renderC(comments,p.id)}</div>
    <div style="background:var(--sf);border:1px solid var(--br);border-radius:12px;padding:18px;margin-top:14px">
      <div style="font-weight:600;margin-bottom:10px">Your Answer</div>
      <textarea class="inp" id="mb" placeholder="Share your knowledge..." rows="4"></textarea>
      <button class="sbtn" style="width:auto;padding:9px 26px" onclick="postComment(${p.id},null)">Post Answer</button>
    </div>`);
}

function renderC(cs,pid,depth=0){
  if(!cs||!cs.length) return '';
  return cs.map(c=>`
    <div class="ci${depth>0?' rep':''}">
      <div class="cmeta">
        <span class="av" style="background:${c.color};width:17px;height:17px;font-size:.53rem;display:inline-flex">${c.username[0].toUpperCase()}</span>
        <strong style="margin-left:5px">${esc(c.username)}</strong>
        <span style="margin-left:7px">${fmtTime(c.created_at)}</span>
        <span style="margin-left:10px;color:var(--ac3)">▲ ${c.score}</span>
      </div>
      <div class="cbody">${esc(c.body)}</div>
      <div style="display:flex;gap:10px;margin-top:7px;align-items:center">
        <button class="vbtn" style="padding:3px 9px;font-size:.75rem" onclick="vote('comment',${c.id},1)">▲ Upvote</button>
        <span class="rl" onclick="toggleR(${c.id})">↩ Reply</span>
      </div>
      <div class="rform" id="rf${c.id}">
        <textarea class="inp" id="rb${c.id}" placeholder="Write a reply..." rows="3" style="margin-top:8px;margin-bottom:8px"></textarea>
        <button class="vbtn" style="padding:6px 14px;background:var(--ac);color:#fff;border-color:var(--ac)" onclick="postComment(${pid},${c.id})">Reply</button>
      </div>
      ${renderC(c.replies,pid,depth+1)}
    </div>`).join('');
}

function countC(cs){ return cs?cs.reduce((a,c)=>a+1+countC(c.replies),0):0; }
function toggleR(id){ const f=$('#rf'+id); f.toggle(); if(f.is(':visible')) $('#rb'+id).focus(); }

function postComment(pid,par){
  if(!me){openM('lm');return;}
  const el=par?'#rb'+par:'#mb';
  const body=$(el).val().trim();
  if(!body){toast('Write something first','er');return;}
  $.ajax({url:'/api/posts/'+pid+'/comments',method:'POST',contentType:'application/json',
    data:JSON.stringify({body,parent_id:par}),
    success(d){
      if(d.ok){
        $(el).val('');
        if(par) $('#rf'+par).hide();
        $.get('/api/posts/'+pid,function(d){
          const nc=countC(d.comments);
          $('#cs').html(renderC(d.comments,pid));
          $('[data-ac]').text(nc+' Answer'+(nc!==1?'s':''));
        });
        toast('Posted! ✅');
      }
    }
  });
}

function vote(type,id,val){
  if(!me){openM('lm');return;}
  const pl=type==='post'?{post_id:id,value:val}:{comment_id:id,value:val};
  $.ajax({url:'/api/vote',method:'POST',contentType:'application/json',data:JSON.stringify(pl),success(){toast('Vote recorded ✓');}});
}

function newPost(){ if(!me){openM('lm');return;} openM('pm'); }

function doPost(){
  const title=$('#pt').val().trim(), body=$('#pb2').val().trim();
  const tags=$('#ptg').val().trim().split(',').map(t=>t.trim()).filter(Boolean);
  $('#pe').hide();
  if(!title||!body){$('#pe').text('Title and body required').show();return;}
  $.ajax({url:'/api/posts',method:'POST',contentType:'application/json',
    data:JSON.stringify({title,body,tags}),
    success(d){
      if(d.ok){ closeM('pm'); $('#pt,#pb2,#ptg').val(''); loadP(1); toast('Question posted! 🎉'); }
    },
    error(x){$('#pe').text(JSON.parse(x.responseText).error).show();}
  });
}

function loadTags(){
  $.get('/api/tags',function(d){
    $('#tc2').html(d.tags.slice(0,10).map(t=>`<span class="tag" onclick="ftag('${esc(t.name)}')">${esc(t.name)} <span style="opacity:.6">${t.count}</span></span>`).join(''));
  });
}

function loadStats(){
  $.get('/api/stats',function(d){ $('#sp').text(d.posts);$('#su').text(d.users);$('#sc2').text(d.comments);$('#st').text(d.tags); });
}

function ftag(name,e){ if(e)e.stopPropagation(); ctag=name; pg=1; $('#atl').text(name); $('#atb').show(); loadP(1); showFeed(); }
function clrTag(){ ctag=''; $('#atb').hide(); loadP(1); }
function showFeed(){ $('#fv').show(); $('#dv').hide(); }

function doLogin(){
  const u=$('#lu').val().trim(), p=$('#lp').val();
  $('#le').hide();
  $.ajax({url:'/api/login',method:'POST',contentType:'application/json',
    data:JSON.stringify({username:u,password:p}),
    success(d){ if(d.ok){ closeM('lm'); checkMe(); toast('Welcome back, '+u+'!'); } },
    error(x){$('#le').text(JSON.parse(x.responseText).error).show();}
  });
}

function doReg(){
  const u=$('#ru').val().trim(), p=$('#rp').val();
  $('#re').hide();
  if(!u||!p){$('#re').text('Both fields required').show();return;}
  $.ajax({url:'/api/register',method:'POST',contentType:'application/json',
    data:JSON.stringify({username:u,password:p}),
    success(d){ if(d.ok){ closeM('rm'); checkMe(); toast('Welcome to MindHive, '+u+'! 🐝'); } },
    error(x){$('#re').text(JSON.parse(x.responseText).error).show();}
  });
}

function openM(id){ document.getElementById(id).classList.add('open'); }
function closeM(id){ document.getElementById(id).classList.remove('open'); }
function switchM(a,b){ closeM(a); openM(b); }
function bgClose(e,id){ if(e.target===document.getElementById(id)) closeM(id); }

function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fmtTime(dt){
  const d=new Date(dt.includes('T')?dt:dt.replace(' ','T')+'Z'), now=new Date(), diff=Math.floor((now-d)/1000);
  if(diff<60) return 'just now';
  if(diff<3600) return Math.floor(diff/60)+'m ago';
  if(diff<86400) return Math.floor(diff/3600)+'h ago';
  if(diff<2592000) return Math.floor(diff/86400)+'d ago';
  return d.toLocaleDateString();
}
function toast(msg,type='ok'){
  const id='t'+Date.now();
  $('#tc').append(`<div class="ti ${type}" id="${id}">${msg}</div>`);
  setTimeout(()=>$('#'+id).fadeOut(300,function(){$(this).remove();}),2800);
}
function dsearch(){ clearTimeout(stimer); stimer=setTimeout(()=>loadP(1),380); }
</script>
</body>
</html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        pr=urlparse(self.path); p=pr.path; qs=parse_qs(pr.query)
        self._cookie=None
        if p in('/','index.html'): return hsend(self,PAGE)
        if p=='/api/me': return self._me()
        if p=='/api/posts': return self._posts(qs)
        if p.startswith('/api/posts/') and not p.endswith('/comments'):
            try: return self._post(int(p.split('/')[-1]))
            except: pass
        if p=='/api/tags': return self._tags()
        if p=='/api/stats': return self._stats()
        jsend(self,{"error":"not found"},404)
    def do_POST(self):
        pr=urlparse(self.path); p=pr.path
        self._cookie=None
        n=int(self.headers.get('Content-Length',0))
        body=self.rfile.read(n)
        u=session_user(self)
        if p=='/api/login': return self._login(body)
        if p=='/api/register': return self._register(body)
        if p=='/api/logout': return self._logout()
        if p=='/api/posts':
            if not u: return jsend(self,{"error":"login required"},401)
            return self._newpost(body,u)
        if p.startswith('/api/posts/') and p.endswith('/comments'):
            if not u: return jsend(self,{"error":"login required"},401)
            try: return self._comment(body,u,int(p.split('/')[-2]))
            except: pass
        if p=='/api/vote':
            if not u: return jsend(self,{"error":"login required"},401)
            return self._vote(body,u)
        jsend(self,{"error":"not found"},404)

    def _me(self):
        u=session_user(self)
        jsend(self,{"user":{"id":u["id"],"username":u["username"],"color":u["color"]} if u else None})
    def _login(self,body):
        d=json.loads(body); c=db()
        row=c.execute("SELECT * FROM users WHERE username=? AND password_hash=?",(d.get("username",""),hpw(d.get("password","")))).fetchone()
        c.close()
        if not row: return jsend(self,{"error":"Wrong username or password"},401)
        self._cookie=f"uid={row['id']}; Path=/; HttpOnly"
        jsend(self,{"ok":True,"username":row["username"]})
    def _register(self,body):
        d=json.loads(body); u=d.get("username","").strip(); p=d.get("password","")
        if len(u)<3: return jsend(self,{"error":"Username must be at least 3 characters"},400)
        if len(p)<4: return jsend(self,{"error":"Password must be at least 4 characters"},400)
        c=db(); colors=["#7C6AF0","#FF6B8A","#43D9B8","#F7931E","#00B4D8","#E84393"]
        try:
            c.execute("INSERT INTO users(username,password_hash,color) VALUES(?,?,?)",(u,hpw(p),random.choice(colors)))
            c.commit(); row=c.execute("SELECT * FROM users WHERE username=?",(u,)).fetchone()
            self._cookie=f"uid={row['id']}; Path=/; HttpOnly"
            jsend(self,{"ok":True,"username":u})
        except sqlite3.IntegrityError: jsend(self,{"error":"Username already taken"},409)
        finally: c.close()
    def _logout(self):
        self._cookie="uid=; Path=/; Max-Age=0"
        jsend(self,{"ok":True})
    def _posts(self,qs):
        pg=int(qs.get("page",["1"])[0]); pp=10
        q=qs.get("q",[""])[0]; tag=qs.get("tag",[""])[0]; srt=qs.get("sort",["newest"])[0]
        wh=[]; pa=[]
        if q: wh.append("(p.title LIKE ? OR p.body LIKE ?)"); pa+=[f"%{q}%",f"%{q}%"]
        if tag: wh.append("p.id IN(SELECT pt.post_id FROM post_tags pt JOIN tags t ON t.id=pt.tag_id WHERE t.name=?)"); pa.append(tag)
        ws=("WHERE "+" AND ".join(wh)) if wh else ""
        od={"newest":"p.created_at DESC","oldest":"p.created_at ASC","popular":"(SELECT COALESCE(SUM(v.value),0) FROM votes v WHERE v.post_id=p.id) DESC","views":"p.views DESC"}.get(srt,"p.created_at DESC")
        c=db()
        total=c.execute(f"SELECT COUNT(*) as n FROM posts p {ws}",pa).fetchone()["n"]
        rows=c.execute(f"SELECT p.*,u.username,u.color FROM posts p JOIN users u ON u.id=p.user_id {ws} ORDER BY {od} LIMIT ? OFFSET ?",pa+[pp,(pg-1)*pp]).fetchall()
        out=[]
        for r in rows:
            nc=c.execute("SELECT COUNT(*) as n FROM comments WHERE post_id=?",(r["id"],)).fetchone()["n"]
            out.append({"id":r["id"],"title":r["title"],"body":r["body"][:200],"username":r["username"],"color":r["color"],"created_at":r["created_at"],"views":r["views"],"score":pscore(c,r["id"]),"comments":nc,"tags":ptags(c,r["id"])})
        c.close()
        jsend(self,{"posts":out,"total":total,"page":pg,"pages":max(1,(total+pp-1)//pp)})
    def _post(self,pid):
        c=db(); c.execute("UPDATE posts SET views=views+1 WHERE id=?",(pid,)); c.commit()
        row=c.execute("SELECT p.*,u.username,u.color FROM posts p JOIN users u ON u.id=p.user_id WHERE p.id=?",(pid,)).fetchone()
        if not row: c.close(); return jsend(self,{"error":"not found"},404)
        post={"id":row["id"],"title":row["title"],"body":row["body"],"username":row["username"],"color":row["color"],"created_at":row["created_at"],"views":row["views"],"score":pscore(c,row["id"]),"tags":ptags(c,row["id"])}
        comms=pcomments(c,pid); c.close()
        jsend(self,{"post":post,"comments":comms})
    def _newpost(self,body,u):
        d=json.loads(body); title=d.get("title","").strip(); text=d.get("body","").strip(); tags=d.get("tags",[])
        if not title or not text: return jsend(self,{"error":"Title and body required"},400)
        c=db(); c.execute("INSERT INTO posts(title,body,user_id) VALUES(?,?,?)",(title,text,u["id"])); c.commit()
        pid=c.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        for tn in tags[:5]:
            tn=tn.strip()
            if not tn: continue
            c.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)",(tn,)); c.commit()
            tid=c.execute("SELECT id FROM tags WHERE name=?",(tn,)).fetchone()["id"]
            c.execute("INSERT OR IGNORE INTO post_tags VALUES(?,?)",(pid,tid))
        c.commit(); c.close()
        jsend(self,{"ok":True,"id":pid})
    def _comment(self,body,u,pid):
        d=json.loads(body); text=d.get("body","").strip(); par=d.get("parent_id")
        if not text: return jsend(self,{"error":"Body required"},400)
        c=db(); c.execute("INSERT INTO comments(body,post_id,user_id,parent_id) VALUES(?,?,?,?)",(text,pid,u["id"],par)); c.commit(); c.close()
        jsend(self,{"ok":True})
    def _vote(self,body,u):
        d=json.loads(body); pid=d.get("post_id"); cid=d.get("comment_id"); val=d.get("value",1)
        c=db()
        try:
            if pid: c.execute("INSERT OR REPLACE INTO votes(user_id,post_id,comment_id,value) VALUES(?,?,NULL,?)",(u["id"],pid,val))
            elif cid: c.execute("INSERT OR REPLACE INTO votes(user_id,post_id,comment_id,value) VALUES(?,NULL,?,?)",(u["id"],cid,val))
            c.commit()
        finally: c.close()
        jsend(self,{"ok":True})
    def _tags(self):
        c=db(); rows=c.execute("SELECT t.name,COUNT(pt.post_id) as cnt FROM tags t LEFT JOIN post_tags pt ON pt.tag_id=t.id GROUP BY t.id ORDER BY cnt DESC").fetchall(); c.close()
        jsend(self,{"tags":[{"name":r["name"],"count":r["cnt"]} for r in rows]})
    def _stats(self):
        c=db()
        jsend(self,{"posts":c.execute("SELECT COUNT(*) as n FROM posts").fetchone()["n"],"users":c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"],"comments":c.execute("SELECT COUNT(*) as n FROM comments").fetchone()["n"],"tags":c.execute("SELECT COUNT(*) as n FROM tags").fetchone()["n"]})
        c.close()

if __name__=='__main__':
    setup()
    s=HTTPServer(('0.0.0.0',8000),H)
    print("\n  MindHive running at http://localhost:8000\n  Login: anchit / pass123\n  Ctrl+C to stop\n")
    try: s.serve_forever()
    except KeyboardInterrupt: pass

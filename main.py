# main.py
from fastapi import FastAPI, Request, Depends, HTTPException, Form, Cookie
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import openpyxl
import os

from database import engine, Base, get_db
import models

Base.metadata.create_all(bind=engine)

app = FastAPI()

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

class PlayerCreate(BaseModel):
    name: str
    team: Optional[str] = ""

class MatchCreate(BaseModel):
    player_a_id: int
    player_b_id: int
    set1: Optional[str] = "-"
    set2: Optional[str] = "-"
    set3: Optional[str] = "-"
    set4: Optional[str] = "-"
    set5: Optional[str] = "-"

# --- ระบบ Login & Logout ---
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # ตรวจสอบชื่อผู้ใช้และรหัสผ่าน
    if username == "kmitl" and password == "2419":
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="is_logged_in", value="true", max_age=86400) # เก็บไว้ 1 วัน
        return response
    
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}
    )

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="is_logged_in")
    return response

# --- หน้าหลัก (ล็อกไว้ ต้อง Login ก่อนเท่านั้น) ---
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, is_logged_in: Optional[str] = Cookie(None)):
    if is_logged_in != "true":
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="index.html")

# --- API Players ---
@app.get("/api/players")
def get_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()

@app.post("/api/players")
def create_player(player: PlayerCreate, db: Session = Depends(get_db)):
    db_player = models.Player(name=player.name, team=player.team)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player

@app.delete("/api/players/{player_id}")
def delete_player(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if player:
        db.delete(player)
        db.commit()
    return {"ok": True}

# --- API Matches ---
@app.get("/api/matches")
def get_matches(db: Session = Depends(get_db)):
    matches = db.query(models.Match).all()
    result = []
    for m in matches:
        p_a = db.query(models.Player).filter(models.Player.id == m.player_a_id).first()
        p_b = db.query(models.Player).filter(models.Player.id == m.player_b_id).first()
        
        sets_list = [s for s in [m.set1, m.set2, m.set3, m.set4, m.set5] if s and s.strip() != "-" and s.strip() != ""]
        sets_detail = ", ".join(sets_list) if sets_list else "-"

        result.append({
            "id": m.id,
            "player_a_name": p_a.name if p_a else "ไม่พบข้อมูล",
            "player_b_name": p_b.name if p_b else "ไม่พบข้อมูล",
            "sets_detail": sets_detail,
            "score_sets": m.score_sets,
            "winner": m.winner_name
        })
    return result

@app.post("/api/matches")
def create_match(match: MatchCreate, db: Session = Depends(get_db)):
    p_a = db.query(models.Player).filter(models.Player.id == match.player_a_id).first()
    p_b = db.query(models.Player).filter(models.Player.id == match.player_b_id).first()

    if not p_a or not p_b:
        raise HTTPException(status_code=400, detail="ไม่พบนักกีฬา")

    sets_a, sets_b = 0, 0
    raw_sets = [match.set1, match.set2, match.set3, match.set4, match.set5]
    
    for s in raw_sets:
        if s and "-" in s:
            try:
                parts = s.split("-")
                score_a = int(parts[0].strip())
                score_b = int(parts[1].strip())
                if score_a > score_b:
                    sets_a += 1
                elif score_b > score_a:
                    sets_b += 1
            except ValueError:
                pass

    score_sets = f"{sets_a} - {sets_b}"
    if sets_a > sets_b:
        winner_name = p_a.name
    elif sets_b > sets_a:
        winner_name = p_b.name
    else:
        winner_name = "เสมอ"

    db_match = models.Match(
        player_a_id=match.player_a_id,
        player_b_id=match.player_b_id,
        set1=match.set1,
        set2=match.set2,
        set3=match.set3,
        set4=match.set4,
        set5=match.set5,
        score_sets=score_sets,
        winner_name=winner_name
    )
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match

@app.delete("/api/matches/{match_id}")
def delete_match(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if match:
        db.delete(match)
        db.commit()
    return {"ok": True}

# --- API Standings ---
@app.get("/api/standings")
def get_standings(db: Session = Depends(get_db)):
    players = db.query(models.Player).all()
    matches = db.query(models.Match).all()

    stats = {p.id: {"name": p.name, "team": p.team or "-", "played": 0, "won": 0, "lost": 0, "sets_won": 0, "sets_lost": 0, "points": 0} for p in players}

    for m in matches:
        if m.player_a_id in stats and m.player_b_id in stats:
            try:
                sa, sb = map(int, m.score_sets.split(" - "))
            except ValueError:
                sa, sb = 0, 0

            stats[m.player_a_id]["played"] += 1
            stats[m.player_b_id]["played"] += 1
            stats[m.player_a_id]["sets_won"] += sa
            stats[m.player_a_id]["sets_lost"] += sb
            stats[m.player_b_id]["sets_won"] += sb
            stats[m.player_b_id]["sets_lost"] += sa

            if sa > sb:
                stats[m.player_a_id]["won"] += 1
                stats[m.player_a_id]["points"] += 2
                stats[m.player_b_id]["lost"] += 1
                stats[m.player_b_id]["points"] += 1
            elif sb > sa:
                stats[m.player_b_id]["won"] += 1
                stats[m.player_b_id]["points"] += 2
                stats[m.player_a_id]["lost"] += 1
                stats[m.player_a_id]["points"] += 1

    standings = []
    for pid, s in stats.items():
        set_diff = s["sets_won"] - s["sets_lost"]
        standings.append({**s, "set_diff": set_diff})

    standings.sort(key=lambda x: (x["points"], x["set_diff"], x["sets_won"]), reverse=True)

    for i, s in enumerate(standings, 1):
        s["rank"] = i

    return standings

@app.get("/api/export-excel")
def export_excel(db: Session = Depends(get_db)):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ตารางคะแนน"
    ws.append(["อันดับ", "ชื่อนักกีฬา", "สังกัด", "แข่ง", "ชนะ", "แพ้", "เซตได้", "เซตเสีย", "ผลต่างเซต", "คะแนนรวม"])
    
    standings = get_standings(db)
    for s in standings:
        ws.append([s["rank"], s["name"], s["team"], s["played"], s["won"], s["lost"], s["sets_won"], s["sets_lost"], s["set_diff"], s["points"]])
        
    file_path = "pingpong_summary.xlsx"
    wb.save(file_path)
    return FileResponse(file_path, filename="สรุปผลปิงปอง.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
# อย่าลืมตรวจสอบว่ามี import Player, Match จาก models และ get_db จาก database แล้วหรือยัง
from models import Player, Match 
from database import get_db 

@app.delete("/api/clear-players")
def clear_players(db: Session = Depends(get_db)):
    try:
        # ลบประวัติการแข่งก่อนเพื่อป้องกันติดปัญหา Foreign Key
        db.query(Match).delete()
        db.query(Player).delete()
        db.commit()
        return {"status": "success", "message": "ลบนักกีฬาและประวัติทั้งหมดเรียบร้อยแล้ว"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/clear-matches")
def clear_matches(db: Session = Depends(get_db)):
    try:
        db.query(Match).delete()
        db.commit()
        return {"status": "success", "message": "ลบประวัติการแข่งขันเรียบร้อยแล้ว"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
import os
import openpyxl
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import FastAPI, Request, Depends, HTTPException, Form, Cookie, Header
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import engine, Base, get_db
import models

# สร้างตารางข้อมูลเมื่อเริ่มต้นแอป
Base.metadata.create_all(bind=engine)

app = FastAPI()

# จัดการโฟลเดอร์ Static และ Templates
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Pydantic Schemas ---
class PlayerCreate(BaseModel):
    name: str
    club: Optional[str] = ""


class MatchCreate(BaseModel):
    player1_id: int
    player2_id: int
    p1_score: int
    p2_score: int


# --- 1. ระบบ Authentication (Login & Logout) ---
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "kmitl" and password == "2419":
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="is_logged_in", value="true", max_age=86400)
        return response

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"},
    )


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="is_logged_in")
    return response


# --- 2. หน้าหลัก (ล็อกเข้าใช้งานด้วย Cookie) ---
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, is_logged_in: Optional[str] = Cookie(None)):
    if is_logged_in != "true":
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="index.html")


# --- 3. API Players (แยกตาม Workspace) ---
@app.get("/api/players")
def get_players(
    x_workspace_id: str = Header("default"), db: Session = Depends(get_db)
):
    return (
        db.query(models.Player)
        .filter(models.Player.workspace_id == x_workspace_id)
        .all()
    )


@app.post("/api/players")
def create_player(
    player: PlayerCreate,
    x_workspace_id: str = Header("default"),
    db: Session = Depends(get_db),
):
    db_player = models.Player(
        name=player.name, club=player.club, workspace_id=x_workspace_id
    )
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player


@app.delete("/api/players/{player_id}")
def delete_player(
    player_id: int,
    x_workspace_id: str = Header("default"),
    db: Session = Depends(get_db),
):
    player = (
        db.query(models.Player)
        .filter(
            models.Player.id == player_id,
            models.Player.workspace_id == x_workspace_id,
        )
        .first()
    )
    if player:
        db.delete(player)
        db.commit()
        return {"ok": True}
    raise HTTPException(status_code=404, detail="ไม่พบนีกกีฬา")


# --- 4. API Matches (แยกตาม Workspace) ---
@app.get("/api/matches")
def get_matches(
    x_workspace_id: str = Header("default"), db: Session = Depends(get_db)
):
    return (
        db.query(models.Match)
        .filter(models.Match.workspace_id == x_workspace_id)
        .all()
    )


@app.post("/api/matches")
def create_match(
    match: MatchCreate,
    x_workspace_id: str = Header("default"),
    db: Session = Depends(get_db),
):
    winner_id = (
        match.player1_id if match.p1_score > match.p2_score else match.player2_id
    )
    db_match = models.Match(
        player1_id=match.player1_id,
        player2_id=match.player2_id,
        p1_score=match.p1_score,
        p2_score=match.p2_score,
        winner_id=winner_id,
        workspace_id=x_workspace_id,
    )
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match


@app.delete("/api/matches/{match_id}")
def delete_match(
    match_id: int,
    x_workspace_id: str = Header("default"),
    db: Session = Depends(get_db),
):
    match = (
        db.query(models.Match)
        .filter(
            models.Match.id == match_id,
            models.Match.workspace_id == x_workspace_id,
        )
        .first()
    )
    if match:
        db.delete(match)
        db.commit()
        return {"ok": True}
    raise HTTPException(status_code=404, detail="ไม่พบประวัติการแข่งขัน")


# --- 5. API Standings (แยกตาม Workspace) ---
@app.get("/api/standings")
def get_standings(
    x_workspace_id: str = Header("default"), db: Session = Depends(get_db)
):
    players = (
        db.query(models.Player)
        .filter(models.Player.workspace_id == x_workspace_id)
        .all()
    )
    matches = (
        db.query(models.Match)
        .filter(models.Match.workspace_id == x_workspace_id)
        .all()
    )

    stats = {
        p.id: {
            "id": p.id,
            "name": p.name,
            "club": p.club or "-",
            "played": 0,
            "won": 0,
            "lost": 0,
            "sets_won": 0,
            "sets_lost": 0,
            "set_diff": 0,
            "pts": 0,
        }
        for p in players
    }

    for m in matches:
        if m.player1_id in stats and m.player2_id in stats:
            stats[m.player1_id]["played"] += 1
            stats[m.player2_id]["played"] += 1
            stats[m.player1_id]["sets_won"] += m.p1_score
            stats[m.player1_id]["sets_lost"] += m.p2_score
            stats[m.player2_id]["sets_won"] += m.p2_score
            stats[m.player2_id]["sets_lost"] += m.p1_score

            if m.winner_id == m.player1_id:
                stats[m.player1_id]["won"] += 1
                stats[m.player1_id]["pts"] += 2
                stats[m.player2_id]["lost"] += 1
                stats[m.player2_id]["pts"] += 1
            else:
                stats[m.player2_id]["won"] += 1
                stats[m.player2_id]["pts"] += 2
                stats[m.player1_id]["lost"] += 1
                stats[m.player1_id]["pts"] += 1

    result = list(stats.values())
    for r in result:
        r["set_diff"] = r["sets_won"] - r["sets_lost"]

    result.sort(key=lambda x: (x["pts"], x["set_diff"], x["sets_won"]), reverse=True)

    for idx, r in enumerate(result, 1):
        r["rank"] = idx

    return result


# --- 6. Export Excel & Clear Data (แยกตาม Workspace) ---
@app.get("/api/export-excel")
def export_excel(
    x_workspace_id: str = Header("default"), db: Session = Depends(get_db)
):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ตารางคะแนน"
    ws.append(
        [
            "อันดับ",
            "ชื่อนักกีฬา",
            "สังกัด",
            "แข่ง",
            "ชนะ",
            "แพ้",
            "เซตได้",
            "เซตเสีย",
            "ผลต่างเซต",
            "คะแนนรวม",
        ]
    )

    standings = get_standings(x_workspace_id=x_workspace_id, db=db)
    for s in standings:
        ws.append(
            [
                s["rank"],
                s["name"],
                s["club"],
                s["played"],
                s["won"],
                s["lost"],
                s["sets_won"],
                s["sets_lost"],
                s["set_diff"],
                s["pts"],
            ]
        )

    file_path = f"pingpong_summary_{x_workspace_id}.xlsx"
    wb.save(file_path)
    return FileResponse(
        file_path,
        filename=f"สรุปผลปิงปอง_{x_workspace_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.delete("/api/clear-players")
def clear_players(
    x_workspace_id: str = Header("default"), db: Session = Depends(get_db)
):
    try:
        db.query(models.Match).filter(
            models.Match.workspace_id == x_workspace_id
        ).delete()
        db.query(models.Player).filter(
            models.Player.workspace_id == x_workspace_id
        ).delete()
        db.commit()
        return {"status": "success", "message": "ลบนักกีฬาและประวัติเฉพาะห้องนี้เรียบร้อยแล้ว"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clear-matches")
def clear_matches(
    x_workspace_id: str = Header("default"), db: Session = Depends(get_db)
):
    try:
        db.query(models.Match).filter(
            models.Match.workspace_id == x_workspace_id
        ).delete()
        db.commit()
        return {"status": "success", "message": "ลบประวัติการแข่งเฉพาะห้องนี้เรียบร้อยแล้ว"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
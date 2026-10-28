
import re
import requests
from datetime import datetime
from html import unescape
from flask import Flask, render_template, request

app = Flask(__name__)

# KBO 10개 구단
teams = [
    {"name": "LG 트윈스", "city": "서울"},
    {"name": "KT 위즈", "city": "수원"},
    {"name": "SSG 랜더스", "city": "인천"},
    {"name": "두산 베어스", "city": "서울"},
    {"name": "KIA 타이거즈", "city": "광주"},
    {"name": "삼성 라이온즈", "city": "대구"},
    {"name": "롯데 자이언츠", "city": "부산"},
    {"name": "한화 이글스", "city": "대전"},
    {"name": "NC 다이노스", "city": "창원"},
    {"name": "키움 히어로즈", "city": "서울"},
]

# KBO 공식 데이터의 팀 이름을 사이트 이름으로 변환
TEAM_NAME_MAP = {
    "LG": "LG 트윈스",
    "KT": "KT 위즈",
    "SSG": "SSG 랜더스",
    "두산": "두산 베어스",
    "KIA": "KIA 타이거즈",
    "삼성": "삼성 라이온즈",
    "롯데": "롯데 자이언츠",
    "한화": "한화 이글스",
    "NC": "NC 다이노스",
    "키움": "키움 히어로즈",
}


def fetch_kbo_games(year, month):
    """KBO 공식 사이트에서 해당 월의 경기 데이터를 가져온다."""

    url = (
        "https://www.koreabaseball.com/"
        "ws/Schedule.asmx/GetScheduleList"
    )

    data = {
        "leId": "1",
        "srIdList": "0,9,6",
        "seasonId": str(year),
        "gameMonth": f"{month:02d}",
        "teamId": "",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": (
            "https://www.koreabaseball.com/"
            "Schedule/Schedule.aspx"
        ),
        "User-Agent": "Mozilla/5.0",
    }

    response = requests.post(
        url,
        data=data,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()

    games = []
    current_date = None

    for row in result.get("rows", []):
        cells = row.get("row", [])

        if not cells:
            continue

        offset = 0

        # 날짜 읽기
        if cells[0].get("Class") == "day":
            date_text = unescape(cells[0].get("Text", ""))
            match = re.search(r"(\d{2})\.(\d{2})", date_text)

            if match:
                current_date = (
                    f"{year}-{int(match.group(1)):02d}-"
                    f"{int(match.group(2)):02d}"
                )

            offset = 1

        if current_date is None:
            continue

        # 경기 정보가 있는지 확인
        if len(cells) <= offset + 1:
            continue

        play_html = cells[offset + 1].get("Text", "")

        teams_match = re.search(
            r"<span>([^<]+)</span><em>(.*?)</em><span>([^<]+)</span>",
            play_html,
        )

        if not teams_match:
            continue

        away_raw = unescape(teams_match.group(1)).strip()
        score_html = teams_match.group(2)
        home_raw = unescape(teams_match.group(3)).strip()

        # 구단 이름을 사이트에서 사용하는 이름으로 변환
        away_team = TEAM_NAME_MAP.get(away_raw, away_raw)
        home_team = TEAM_NAME_MAP.get(home_raw, home_raw)

        # 경기 점수 읽기
        score_match = re.search(
            r"<span[^>]*>(\d+)</span>\s*"
            r"<span>vs</span>\s*"
            r"<span[^>]*>(\d+)</span>",
            score_html,
        )

        away_score = (
            int(score_match.group(1)) if score_match else None
        )
        home_score = (
            int(score_match.group(2)) if score_match else None
        )

        # 경기 시간 읽기
        time_html = cells[offset].get("Text", "")
        time_match = re.search(r"(\d{1,2}:\d{2})", time_html)
        game_time = time_match.group(1) if time_match else "-"

        # 경기장 정보가 있으면 읽기
        stadium = ""
        for cell in cells:
            cell_text = unescape(
                re.sub(r"<[^>]+>", " ", cell.get("Text", ""))
            ).strip()

            if any(
                place in cell_text
                for place in (
                    "잠실", "고척", "문학", "수원", "대전",
                    "대구", "광주", "사직", "창원", "포항", "울산"
                )
            ):
                stadium = cell_text
                break

        games.append({
            "date": current_date,
            "time": game_time,
            "away": away_team,
            "home": home_team,
            "away_score": away_score,
            "home_score": home_score,
            "stadium": stadium,
        })

    return games


@app.route("/")
def home():
    selected_date = request.args.get("date", "").strip()
    selected_team = request.args.get("team", "").strip()

    today = datetime.now()

    # 선택한 날짜의 연도와 월 가져오기
    try:
        if selected_date:
            chosen_date = datetime.strptime(
                selected_date, "%Y-%m-%d"
            )
            year = chosen_date.year
            month = chosen_date.month
        else:
            year = today.year
            month = today.month

    except ValueError:
        selected_date = ""
        year = today.year
        month = today.month

    # 실제 KBO 경기 데이터 가져오기
    try:
        games = fetch_kbo_games(year, month)

    except Exception as e:
        print("KBO 경기 데이터 조회 실패:", e)
        games = []

    # 팀별 순위 초기화
    standings = {}

    for team in teams:
        standings[team["name"]] = {
            "name": team["name"],
            "city": team["city"],
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "games": 0,
            "win_rate": 0.0,
        }

    # 경기 결과를 이용해 순위 계산
    for game in games:
        home_score = game["home_score"]
        away_score = game["away_score"]

        if home_score is None or away_score is None:
            continue

        home_team = standings.get(game["home"])
        away_team = standings.get(game["away"])

        if home_team is None or away_team is None:
            continue

        home_team["games"] += 1
        away_team["games"] += 1

        if home_score > away_score:
            home_team["wins"] += 1
            away_team["losses"] += 1

        elif home_score < away_score:
            away_team["wins"] += 1
            home_team["losses"] += 1

        else:
            home_team["draws"] += 1
            away_team["draws"] += 1

    # 승률 계산
    for team in standings.values():
        decisions = team["wins"] + team["losses"]

        if decisions > 0:
            team["win_rate"] = team["wins"] / decisions

    sorted_standings = sorted(
        standings.values(),
        key=lambda team: team["win_rate"],
        reverse=True,
    )

    # 날짜 및 구단별 경기 필터링
    filtered_games = []

    for game in games:
        if selected_date and game["date"] != selected_date:
            continue

        if selected_team and (
            game["home"] != selected_team
            and game["away"] != selected_team
        ):
            continue

        filtered_games.append(game)

    # HTML 페이지로 데이터 전달
    return render_template(
        "index.html",
        teams=teams,
        games=filtered_games,
        standings=sorted_standings,
        selected_date=selected_date,
        selected_team=selected_team,
    )


if __name__ == "__main__":
    app.run(debug=True)

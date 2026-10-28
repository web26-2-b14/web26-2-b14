
import requests

url = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"

data = {
    "leId": "1",
    "srIdList": "0,9,6",
    "seasonId": "2026",
    "gameMonth": "10",
    "teamId": ""
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.koreabaseball.com/Schedule/Schedule.aspx",
    "User-Agent": "Mozilla/5.0"
}

try:
    response = requests.post(
        url,
        data=data,
        headers=headers,
        timeout=20
    )

    print("응답 코드:", response.status_code)
    response.raise_for_status()

    result = response.json()
    print("데이터 응답:")
    print(str(result)[:3000])

except Exception as e:
    print("오류 발생:", e)

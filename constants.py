# 구단 계보 (이름이 달라도 같은 팀)
TEAM_GROUPS = [
    ["Hanwha", "Binggrae", "한화", "빙그레"],
    ["SSG", "SK", "에스에스지", "에스케이"],
    ["KIA", "Haitai", "기아", "해태"],
    ["Doosan", "OB", "두산", "오비"],
    ["Hyundai", "Pacific", "Sammi", "Chungbo", "현대", "태평양", "삼미", "청보"],
    ["LG", "MBC", "엘지", "엠비씨"],
    ["Kiwoom", "Nexen", "키움", "넥센"]
]

# 데이터 파일 및 시트
PLAYER_DB_GLOB = "9UP 프로야구_선수DB_*.xlsx"

DATA_FILES = {
    "players": "9UP 프로야구_선수DB_202603_ver.3.xlsx",
    "skills": "9UP 프로야구 스킬 정보.xlsx",
    "careers": "9UP 프로야구 커리어 정보.xlsx",
}

DATA_SHEETS = {
    "pitcher": "투수",
    "batter": "타자",
    "extra_pitcher": "추가투수",
    "extra_batter": "추가타자",
}

# 돌파 상수
BT_BASE_VALS = {
    1: {1: 30, 2: 90},
    2: {1: 30, 2: 90, 3: 180},
    3: {1: 30, 2: 90, 3: 180, 4: 300},
    4: {1: 30, 2: 90, 3: 180, 4: 300, 5: 450},
}

BT_RARITY_5_DATA = {
    "GROUP_1": ["SEA", "POS", "AGS"],
    "GROUP_1_VALS": {1: 30, 2: 90, 3: 180, 4: 300, 5: 450, 6: 630},
    "GROUP_2": ["MMVP", "TEA", "ROY"],
    "GROUP_2_VALS": {1: 50, 2: 150, 3: 300, 4: 500, 5: 750, 6: 1050},
    "GROUP_3": ["ACE", "TOP", "GG", "HIT", "GOY"],
    "GROUP_3_VALS": {1: 100, 2: 250, 3: 450, 4: 700, 5: 1050, 6: 1500},
}

# 등급별 도감/강화 상수
GRADE_CONSTANTS = {
    "SEA": {"atlas": 80, "enhance": 30}, "AGS": {"atlas": 80, "enhance": 30},
    "POS": {"atlas": 80, "enhance": 40}, "ROY": {"atlas": 100, "enhance": 50},
    "MMVP": {"atlas": 90, "enhance": 40}, "TEA": {"atlas": 90, "enhance": 40},
    "GOY": {"atlas": 90, "enhance": 50}, "ACE": {"atlas": 90, "enhance": 50},
    "HIT": {"atlas": 90, "enhance": 50}, "TOP": {"atlas": 120, "enhance": 50},
    "DGN": {"atlas": 0, "enhance": 300}, "GG": {"atlas": 100, "enhance": 50},
}

# 그래프 순서 및 연산 대상 (사용자 요청 순서 반영)
P_GRAPH_ORDER = ["무브먼트", "홈런 억제", "스터프", "컨트롤", "장타 억제"]
B_GRAPH_ORDER = ["컨택", "홈런 파워", "삼진회피", "선구", "갭 파워"]
PITCHER_STATS = P_GRAPH_ORDER + ["한계투구", "주자견제", "수비"]
BATTER_STATS = B_GRAPH_ORDER + ["도루", "주루", "수비"]

STAT_MAP = {
    "컨택트": "컨택", "컨택": "컨택", "삼진 회피": "삼진회피", "삼진회피": "삼진회피",
    "홈런 파워": "홈런 파워", "갭 파워": "갭 파워", "선구": "선구", "수비": "수비",
    "주루": "주루", "도루": "도루", "무브먼트": "무브먼트", "장타 억제": "장타 억제",
    "홈런 억제": "홈런 억제", "컨트롤": "컨트롤", "스터프": "스터프", "한계투구": "한계투구", "주자견제": "주자견제"
}

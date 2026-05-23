import pandas as pd
import streamlit as st
import re
import plotly.graph_objects as go
import json
from pathlib import Path
import hashlib
from logic import calculate_career_bonuses, calculate_final_stats

# ==========================================
# 1. 정밀 교정된 시스템 데이터
# ==========================================
BT_BASE_VALS = {
    1: {1: 30, 2: 90}, 2: {1: 30, 2: 90, 3: 180}, 
    3: {1: 30, 2: 90, 3: 180, 4: 300}, 4: {1: 30, 2: 90, 3: 180, 4: 300, 5: 450}
}
BT_RARITY_5_DATA = {
    "GROUP_1": ["SEA", "POS", "AGS"], "GROUP_1_VALS": {1: 30, 2: 90, 3: 180, 4: 300, 5: 450, 6: 630},
    "GROUP_2": ["MMVP", "TEA", "ROY"], "GROUP_2_VALS": {1: 50, 2: 150, 3: 300, 4: 500, 5: 750, 6: 1050},
    "GROUP_3": ["ACE", "TOP", "GG", "HIT"], "GROUP_3_VALS": {1: 100, 2: 250, 3: 450, 4: 700, 5: 1050, 6: 1500}
}
GRADE_CONSTANTS = {
    "SEA": {"atlas": 80, "enhance": 30}, "AGS": {"atlas": 80, "enhance": 30},
    "POS": {"atlas": 80, "enhance": 40}, "ROY": {"atlas": 100, "enhance": 50},
    "MMVP": {"atlas": 90, "enhance": 40}, "TEA": {"atlas": 90, "enhance": 40},
    "GG": {"atlas": 90, "enhance": 50}, "ACE": {"atlas": 90, "enhance": 50},
    "HIT": {"atlas": 90, "enhance": 50}, "TOP": {"atlas": 120, "enhance": 50},
    "DGN": {"atlas": 0, "enhance": 300}
}
P_GRAPH_ORDER = ['무브먼트', '홈런 억제', '스터프', '컨트롤', '장타 억제']
B_GRAPH_ORDER = ['컨택', '홈런 파워', '삼진회피', '선구', '갭 파워']
PITCHER_STATS = P_GRAPH_ORDER + ['한계투구', '주자견제', '수비']
BATTER_STATS = B_GRAPH_ORDER + ['도루', '주루', '수비']
STAT_MAP = {"컨택트": "컨택", "삼진 회피": "삼진회피", "홈런 파워": "홈런 파워", "갭 파워": "갭 파워", "선구": "선구", "수비": "수비", "무브먼트": "무브먼트", "장타 억제": "장타 억제", "홈런 억제": "홈런 억제", "컨트롤": "컨트롤", "스터프": "스터프", "한계투구": "한계투구", "주자견제": "주자견제"}

# ==========================================
# 2. 유틸리티 함수
# ==========================================
def is_same_team(team1, team2):
    t1, t2 = str(team1).strip().lower(), str(team2).strip().lower()
    if t1 == t2: return True
    gs = [["Hanwha", "Binggrae", "한화", "빙그레"], ["SSG", "SK", "에스에스지", "에스케이"], ["KIA", "Haitai", "기아", "해태"], ["Doosan", "OB", "두산", "오비"], ["Hyundai", "Pacific", "Sammi", "Chungbo", "현대", "태평양", "삼미", "청보"], ["LG", "MBC", "엘지", "엠비씨"], ["Kiwoom", "Nexen", "키움", "넥센"]]
    for g in gs:
        if any(n.lower() in t1 for n in g) and any(n.lower() in t2 for n in g): return True
    return False

@st.cache_data
def load_all_data():
    try:
        player_dbs = sorted(
            Path('.').glob('9UP 프로야구_선수DB_*.xlsx'),
            key=lambda p: (
                int(re.search(r'_(\d{6})', p.name).group(1))
                if re.search(r'_(\d{6})', p.name)
                else 0,
                p.stat().st_mtime,
            ),
            reverse=True,
        )
        if not player_dbs:
            raise FileNotFoundError("9UP 프로야구_선수DB_*.xlsx 파일을 찾을 수 없습니다.")
        p_db, s_db, c_db = player_dbs[0], '9UP 프로야구 스킬 정보.xlsx', '9UP 프로야구 커리어 정보.xlsx'
        return {"p_p": pd.read_excel(p_db, sheet_name='투수'), "p_b": pd.read_excel(p_db, sheet_name='타자'), "s_p": pd.read_excel(s_db, sheet_name='투수'), "s_b": pd.read_excel(s_db, sheet_name='타자'), "c_p": pd.read_excel(c_db, sheet_name='투수'), "c_b": pd.read_excel(c_db, sheet_name='타자'), "c_ex_p": pd.read_excel(c_db, sheet_name='추가투수'), "c_ex_b": pd.read_excel(c_db, sheet_name='추가타자')}
    except Exception as e:
        st.error(f"데이터 파일 로드 실패: {e}"); return None

def get_safe_index(item_list, target_value):
    try:
        items = [str(x) for x in item_list]
        return items.index(str(target_value)) if str(target_value) in items else 0
    except: return 0

def get_number_state(key, default=0):
    try:
        return float(st.session_state.get(key, default))
    except (TypeError, ValueError):
        return default

def format_stage_summary(power=0, stats=0):
    parts = []
    if power:
        parts.append(f"파워 +{power:,.0f}")
    if stats:
        parts.append(f"스탯 +{stats:,.1f}")
    return " / ".join(parts) if parts else "획득 없음"

def get_career_options(career_db, grade):
    db_opts = list(career_db[career_db['등급'] == grade]['옵션'].dropna().unique())
    ordered_opts = ["미개방"]
    if "동일팀파워" in db_opts:
        ordered_opts.append("동일팀파워")
    ordered_opts.extend([opt for opt in db_opts if opt != "동일팀파워"])
    return ordered_opts

def build_career_slots_from_state(career_db):
    c_slots, opt_counts = [], {}
    for i in range(6):
        g_opts = ["마스터"] if i == 5 else ["루키", "프로", "엘리트", "마스터"]
        default_grade = "마스터" if i == 5 else "루키"
        grade = st.session_state.get(f"g{i}", default_grade)
        if grade not in g_opts:
            grade = default_grade

        options = get_career_options(career_db, grade)
        opt = st.session_state.get(f"o{i}", "미개방")
        if opt not in options:
            opt = "미개방"

        amount = 0
        if opt != "미개방":
            vals = career_db[(career_db['등급'] == grade) & (career_db['옵션'] == opt)]['상승량'].tolist()
            if vals:
                saved_amount = st.session_state.get(f"a{i}", vals[0])
                amount = vals[get_safe_index(vals, saved_amount)]

        c_slots.append({"옵션": opt, "상승량": amount})
        opt_counts[opt] = opt_counts.get(opt, 0) + 1
    return c_slots, opt_counts

def get_selected_skills_from_state(player, skill_db):
    avail_skills = ["없음"] + [s.strip() for s in str(player['스킬']).split(',')] if pd.notna(player['스킬']) else ["없음"]
    selected_names = [st.session_state.get(key, "없음") for key in ["sk1", "sk2", "sk3"]]
    used_skills = []
    for name in selected_names:
        if name == "없음" or name not in avail_skills:
            continue
        match = skill_db[skill_db['이름'] == name]
        if not match.empty:
            used_skills.append(match.iloc[0])
    return used_skills

def apply_uploaded_settings(uploaded_file):
    raw_data = uploaded_file.getvalue()
    file_hash = hashlib.md5(raw_data).hexdigest()
    if st.session_state.get("_loaded_settings_hash") == file_hash:
        return

    settings = json.loads(raw_data.decode("utf-8-sig"))
    if "selected_card_label" not in settings and "card_label" in settings:
        settings["selected_card_label"] = settings["card_label"]
    for key, value in settings.items():
        st.session_state[key] = value

    st.session_state["_loaded_settings_hash"] = file_hash
    st.session_state["_settings_loaded"] = True
    st.rerun()

# ==========================================
# 3. 앱 레이아웃 및 설정
# ==========================================
st.set_page_config(page_title="9UP 시뮬 v21.1", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.row-widget.stRadio > div{flex-direction:row;}</style>", unsafe_allow_html=True)
st.title("⚾ 9UP 프로야구 통합 시뮬레이터 v21.1")

data = load_all_data()

if 'init_21_1' not in st.session_state:
    st.session_state['init_21_1'] = True
    defaults = {'p_lv': 100, 'c_lv': 100, 'car_lv': 150, 'atl_lv': 0, 'enh_lv': 0, 'bt_lv': 0, 'eng_p1': 0, 'eng_p2': 0}
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

if data:
    with st.sidebar:
        st.header("📂 데이터 관리")
        uploaded = st.file_uploader("JSON 설정 불러오기", type="json")
        if uploaded:
            apply_uploaded_settings(uploaded)
        if st.session_state.pop("_settings_loaded", False):
            st.success("데이터 로드 완료!")
        st.divider()
        st.header("🔍 검색 및 팀 설정")
        name_in = st.text_input("선수명", key="player_name_input")
        grade_fil = st.selectbox("등급 필터", ["전체"] + list(GRADE_CONSTANTS.keys()), key="grade_filter")
        user_team = st.selectbox("내 구단 설정", sorted(list(set(data['p_p']['구단'].dropna()))), key="user_team_select")
        team_count = st.number_input("같은 팀원 수 (1~28)", 1, 28, key="team_count")

    def find_player():
        p, b = data['p_p'].copy(), data['p_b'].copy()
        if name_in: p, b = p[p['이름'].str.contains(name_in, na=False)], b[b['이름'].str.contains(name_in, na=False)]
        if grade_fil != "전체": p, b = p[p['등급'] == grade_fil], b[b['등급'] == grade_fil]
        p['구분'], b['구분'] = '투수', '타자'
        res = pd.concat([p, b], ignore_index=True)
        if len(res) > 0:
            res['label'] = res.apply(lambda x: f"[{str(x['연도'])}] {x['구단']} {x['이름']} ({x['등급']})", axis=1)
            choice_idx = get_safe_index(res['label'].tolist(), st.session_state.get('selected_card_label', ""))
            return res[res['label'] == st.selectbox("분석 대상 선택", res['label'].tolist(), index=choice_idx, key="selected_card_label")].iloc[0]
        return None

    player = find_player()

    if player is not None:
        p_type, p_grade, p_team, base_p = player['구분'], player['등급'], player['구단'], player['POWER']
        p_cost = int(player.get('코스트', player.get('COST', 0))) 
        target_stats = PITCHER_STATS if p_type == '투수' else BATTER_STATS
        graph_labels = P_GRAPH_ORDER if p_type == '투수' else B_GRAPH_ORDER
        skill_db, career_db, ex_db = (data['s_p'], data['c_p'], data['c_ex_p']) if p_type == '투수' else (data['s_b'], data['c_b'], data['c_ex_b'])

        current_p_lv = get_number_state('p_lv', 100)
        current_c_lv = get_number_state('c_lv', 100)
        current_car_lv = get_number_state('car_lv', 150)
        current_atl_lv = get_number_state('atl_lv', 0)
        current_enh_lv = min(get_number_state('enh_lv', 0), 10 if p_grade == "DGN" else 15)
        current_cl_bonus = (min(current_c_lv, 50)*10 + (max(0, current_c_lv-75))*10) if is_same_team(p_team, user_team) else (min(max(0, current_c_lv-50), 25)*10 + (max(0, current_c_lv-75))*10)
        stage1_power_gain = ((current_p_lv-1)*10) + current_cl_bonus + (current_car_lv-1) + (GRADE_CONSTANTS[p_grade]['atlas']*current_atl_lv) + (GRADE_CONSTANTS[p_grade]['enhance']*current_enh_lv)
        current_weight_p = base_p + stage1_power_gain

        current_c_slots, current_opt_counts = build_career_slots_from_state(career_db)
        stage2_power_gain, current_career_stat_bonus = calculate_career_bonuses(current_c_slots, current_opt_counts, ex_db, target_stats, team_count)
        stage2_stat_gain = sum(current_career_stat_bonus.values())

        current_used_skills = get_selected_skills_from_state(player, skill_db)
        current_p_syn = get_number_state('p_syn', 0)
        current_c_syn = get_number_state('c_syn', 0)
        current_buff = get_number_state('buff', 0)
        stage3_syn_power = int(current_weight_p * (current_p_syn / 100)) + current_c_syn
        stage3_special_power = (32 * team_count) if p_grade in ['ACE', 'HIT'] else 0
        stage3_skill_power = sum([int(current_weight_p * (sk['파워']/100)) for sk in current_used_skills if '파워' in sk and pd.notna(sk['파워'])])
        stage3_power_gain = stage3_syn_power + stage3_special_power + stage3_skill_power + current_buff

        current_eng_pct = get_number_state('eng_p1', 0) + get_number_state('eng_p2', 0)
        current_mid_power_pre = current_weight_p + stage2_power_gain + stage3_power_gain
        stage4_power_gain = int(current_mid_power_pre * (current_eng_pct / 100))
        stage4_stat_gain = sum(get_number_state(f"e1_{stat}", 0) + get_number_state(f"e2_{stat}", 0) for stat in target_stats)

        current_clan_lv = get_number_state('clan_lv', 0)
        current_binder_lv = get_number_state('binder_lv', 0)
        binder_keys = ["b_team", "b_pos", "b_pers", "b_year", "b_grad"]
        current_binder_cat_sum = sum(get_number_state(key, 0) for key in binder_keys)
        stage5_stat_gain = current_clan_lv + (current_binder_lv * 5) + current_binder_cat_sum

        stage6_stat_gain = 0
        if not (p_grade == "DGN" or p_cost >= 6 or p_cost == 0):
            if p_cost == 5:
                current_bt_key = "GROUP_1" if p_grade in BT_RARITY_5_DATA["GROUP_1"] else ("GROUP_3" if p_grade in BT_RARITY_5_DATA["GROUP_3"] else "GROUP_2")
                current_bt_data = BT_RARITY_5_DATA[current_bt_key + "_VALS"]
            else:
                current_bt_data = BT_BASE_VALS.get(p_cost, {})
            stage6_stat_gain = current_bt_data.get(st.session_state.get('bt_lv', 0), 0)

        st.success(f"🎯 분석 대상: [{str(player['연도'])}] {p_team} {player['이름']} ({p_grade} / {p_cost}코스트)")
        col_in, col_res = st.columns([1.4, 1.1])

        with col_in:
            # 1단계: 육성
            st.caption(f"1단계 획득: {format_stage_summary(power=stage1_power_gain)}")
            with st.expander("🛠️ 1단계: 선수 육성 및 강화", expanded=False):
                l1, l2, l3 = st.columns(3)
                p_lv, c_lv, car_lv = l1.number_input("선수레벨", 1, 100, key="p_lv"), l2.number_input("구단레벨", 1, 100, key="c_lv"), l3.number_input("커리어레벨", 1, 150, key="car_lv")
                atl_lv, max_e = st.slider("도감 단계", 0, 10, key="atl_lv"), (10 if p_grade == "DGN" else 15)
                if st.session_state.get('enh_lv', 0) > max_e: st.session_state['enh_lv'] = max_e
                enh_lv = st.slider("강화 단계", 0, max_e, key="enh_lv")
                cl_bonus = (min(c_lv, 50)*10 + (max(0, c_lv-75))*10) if is_same_team(p_team, user_team) else (min(max(0, c_lv-50), 25)*10 + (max(0, c_lv-75))*10)
                weight_p = base_p + ((p_lv-1)*10) + cl_bonus + (car_lv-1) + (GRADE_CONSTANTS[p_grade]['atlas']*atl_lv) + (GRADE_CONSTANTS[p_grade]['enhance']*enh_lv)

            # 2단계: 커리어 ([수정] 미개방 옵션 추가)
            st.caption(f"2단계 획득: {format_stage_summary(power=stage2_power_gain, stats=stage2_stat_gain)}")
            with st.expander("🧬 2단계: 커리어 슬롯 설정", expanded=False):
                c_slots, opt_counts = [], {}
                for i in range(6):
                    st.markdown(f"**📍 슬롯 {i+1}**")
                    g_opts = ["마스터"] if i == 5 else ["루키", "프로", "엘리트", "마스터"]
                    grade = st.radio(f"등급_{i}", g_opts, index=get_safe_index(g_opts, st.session_state.get(f"g{i}", "마스터" if i==5 else "루키")), key=f"g{i}", horizontal=True, label_visibility="collapsed")
                    
                    # 미개방 다음에 선호도가 높은 동일팀파워를 고정 배치
                    opts_with_none = get_career_options(career_db, grade)
                    
                    c1, c2 = st.columns([2, 1])
                    opt = c1.selectbox(f"옵션_{i}", opts_with_none, index=get_safe_index(opts_with_none, st.session_state.get(f"o{i}", "미개방")), key=f"o{i}")
                    
                    if opt == "미개방":
                        vals, amt = [0], 0
                        c2.selectbox(f"수치_{i}", vals, index=0, key=f"a{i}", disabled=True)
                    else:
                        vals = career_db[(career_db['등급'] == grade) & (career_db['옵션'] == opt)]['상승량'].tolist()
                        amt = c2.selectbox(f"수치_{i}", vals, index=get_safe_index(vals, st.session_state.get(f"a{i}", vals[0])), key=f"a{i}")
                    
                    c_slots.append({"옵션": opt, "상승량": amt})
                    opt_counts[opt] = opt_counts.get(opt, 0) + 1
                    if i < 5: st.divider()
                
                career_p_inc, career_stat_bonus = calculate_career_bonuses(c_slots, opt_counts, ex_db, target_stats, team_count)

            # 3단계: 스킬
            st.caption(f"3단계 획득: {format_stage_summary(power=stage3_power_gain)}")
            with st.expander("🔮 3단계: 스킬 및 시너지 설정", expanded=False):
                avail_s = ["없음"] + [s.strip() for s in str(player['스킬']).split(',')] if pd.notna(player['스킬']) else ["없음"]
                sk1, sk2, sk3 = st.selectbox("스킬1", avail_s, key="sk1"), st.selectbox("스킬2", avail_s, key="sk2"), st.selectbox("스킬3", avail_s, key="sk3")
                used_s = [skill_db[skill_db['이름'] == n].iloc[0] for n in [sk1, sk2, sk3] if n != "없음"]
                p_syn, c_syn, buff = st.number_input("% 시너지", 0, key="p_syn"), st.number_input("상수 시너지", 0, key="c_syn"), st.number_input("기타 버프", 0, key="buff")
                syn_p = int(weight_p * (p_syn / 100)) + c_syn
                sp_sk_p = (32 * team_count) if p_grade in ['ACE', 'HIT'] else 0
                sk_p_inc_only = sum([int(weight_p * (sk['파워']/100)) for sk in used_s if '파워' in sk and pd.notna(sk['파워'])])

            # 4단계: 각인 ([수정] 각인 파워 1, 2 정수화)
            st.caption(f"4단계 획득: {format_stage_summary(power=stage4_power_gain, stats=stage4_stat_gain)}")
            with st.expander("💎 4단계: 각인 및 각인 파워 설정", expanded=False):
                st.markdown("### ⚡ 각인 파워 (%)")
                c1, c2 = st.columns(2)
                p_opts = [0, 1, 2, 3]
                eng_p1 = c1.selectbox("각인 1 파워 (%)", p_opts, index=get_safe_index(p_opts, st.session_state.get('eng_p1', 0)), key="eng_p1")
                eng_p2 = c2.selectbox("각인 2 파워 (%)", p_opts, index=get_safe_index(p_opts, st.session_state.get('eng_p2', 0)), key="eng_p2")
                
                st.divider()
                st.markdown("### 🛡️ 스탯 각인")
                eng_stats = {}
                e1, e2 = st.columns(2)
                for idx, stat in enumerate(target_stats):
                    with (e1 if idx < 4 else e2):
                        v1, v2 = st.number_input(f"{stat} S1", 0, key=f"e1_{stat}"), st.number_input(f"{stat} S2", 0, key=f"e2_{stat}")
                        eng_stats[stat] = v1 + v2

            # 5단계: 클랜/바인더
            st.caption(f"5단계 획득: {format_stage_summary(stats=stage5_stat_gain)}")
            with st.expander("🏛️ 5단계: 클랜 및 바인더 설정", expanded=False):
                bc1, bc2 = st.columns(2)
                clan_lv, binder_lv = bc1.slider("클랜 레벨", 0, 15, key="clan_lv"), bc2.number_input("바인더 레벨", 0, 100, key="binder_lv")
                cat_cols, cat_v, b_res = st.columns(5), [0, 10, 17, 22, 25, 27], []
                for i, name in enumerate(["b_team", "b_pos", "b_pers", "b_year", "b_grad"]):
                    v = cat_cols[i].selectbox(name.split('_')[1], cat_v, key=name); b_res.append(v)
                binder_cat_sum = sum(b_res)

            # 6단계: 돌파
            st.caption(f"6단계 획득: {format_stage_summary(stats=stage6_stat_gain)}")
            with st.expander("🔓 6단계: 돌파 설정", expanded=False):
                bt_total = 0
                if p_grade == "DGN" or p_cost >= 6 or p_cost == 0: st.warning("돌파 불가")
                else:
                    if p_cost == 5:
                        bt_k = "GROUP_1" if p_grade in BT_RARITY_5_DATA["GROUP_1"] else ("GROUP_3" if p_grade in BT_RARITY_5_DATA["GROUP_3"] else "GROUP_2")
                        rar_data = BT_RARITY_5_DATA[bt_k + "_VALS"]
                    else: rar_data = BT_BASE_VALS.get(p_cost, {})
                    steps = [0] + [s for s in rar_data.keys() if s <= p_cost + 1]
                    bt_lv = st.selectbox("돌파 단계", steps, index=get_safe_index(steps, st.session_state.get('bt_lv', 0)), key="bt_lv")
                    bt_total = rar_data.get(bt_lv, 0)

            st.divider()
            exclude = ['config', 'init_21_1', '_loaded_settings_hash', '_settings_loaded']
            st.download_button("💾 설정 저장 (JSON)", data=json.dumps({k: v for k, v in st.session_state.items() if k not in exclude}, ensure_ascii=False, indent=4), file_name=f"9UP_Save_{player['이름']}_{p_grade}.json", mime="application/json")

        # --- [연산 엔진: UI 상태와 분리된 순수 계산 로직] ---
        eng_p_total_pct = eng_p1 + eng_p2
        calc_result = calculate_final_stats(
            player=player,
            target_stats=target_stats,
            used_skills=used_s,
            career_stat_bonus=career_stat_bonus,
            eng_stats=eng_stats,
            base_power=base_p,
            weight_power=weight_p,
            syn_power=syn_p,
            special_skill_power=sp_sk_p,
            skill_power_bonus=sk_p_inc_only,
            career_power_bonus=career_p_inc,
            buff=buff,
            engraving_power_pct=eng_p_total_pct,
            clan_level=clan_lv,
            binder_level=binder_lv,
            binder_category_sum=binder_cat_sum,
            breakthrough_total=bt_total,
        )
        eng_p_bonus = calc_result["engraving_power_bonus"]
        final_stats = calc_result["final_stats"]

        with col_res:
            st.subheader("📊 실전 분석 리포트")
            radar_labels = [f"{l}<br><b>{final_stats[l]:.1f}</b>" for l in graph_labels]
            radar_r = [final_stats[l] for l in graph_labels]
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=radar_r + [radar_r[0]], theta=radar_labels + [radar_labels[0]], fill='toself', fillcolor='rgba(255, 215, 0, 0.4)', line=dict(color='#FFD700', width=4)))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, max(final_stats.values())*1.2]), angularaxis=dict(rotation=90, direction="clockwise", tickfont=dict(size=13, color="#ffffff"))), showlegend=False, height=500, margin=dict(t=80, b=50))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"""<div style="background-color: #ff9900; padding: 25px; border-radius: 15px; text-align: center; border: 5px solid #cc7700;"><span style="color: white; font-size: 1.2rem; font-weight: bold;">최종 실전 파워</span><br><span style="color: white; font-size: 4rem; font-weight: 1000;">{sum(final_stats.values()):,.0f}</span></div>""", unsafe_allow_html=True)
            if eng_p_total_pct > 0:
                st.info(f"⚡ 각인 파워 합계 {eng_p_total_pct}% 적용: +{eng_p_bonus:,.0f} 파워 상승")
            st.table(pd.DataFrame([{"항목": c, "최종": f"{final_stats[c]:,.1f}", "상승": f"+{final_stats[c]-player[c]:,.1f}"} for c in target_stats]))

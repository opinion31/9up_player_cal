import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import json
import re
from pathlib import Path
from constants import (
    BATTER_STATS,
    B_GRAPH_ORDER,
    BT_BASE_VALS,
    BT_RARITY_5_DATA,
    DATA_FILES,
    DATA_SHEETS,
    GRADE_CONSTANTS,
    PITCHER_STATS,
    P_GRAPH_ORDER,
    PLAYER_DB_GLOB,
    STAT_MAP,
)
from logic import is_same_team

# ==========================================
# 2. 유틸리티 함수
# ==========================================
def get_latest_player_db():
    files = list(Path(".").glob(PLAYER_DB_GLOB))
    if not files:
        return DATA_FILES["players"]

    def version_key(path):
        numbers = [int(match) for match in re.findall(r"\d+", path.stem)]
        return (numbers, path.stat().st_mtime)

    return str(max(files, key=version_key))

@st.cache_data
def load_all_data():
    try:
        p_db, s_db, c_db = get_latest_player_db(), DATA_FILES["skills"], DATA_FILES["careers"]
        p_sheet, b_sheet = DATA_SHEETS["pitcher"], DATA_SHEETS["batter"]
        return {
            "p_p": pd.read_excel(p_db, sheet_name=p_sheet),
            "p_b": pd.read_excel(p_db, sheet_name=b_sheet),
            "s_p": pd.read_excel(s_db, sheet_name=p_sheet),
            "s_b": pd.read_excel(s_db, sheet_name=b_sheet),
            "c_p": pd.read_excel(c_db, sheet_name=p_sheet),
            "c_b": pd.read_excel(c_db, sheet_name=b_sheet),
            "c_ex_p": pd.read_excel(c_db, sheet_name=DATA_SHEETS["extra_pitcher"]),
            "c_ex_b": pd.read_excel(c_db, sheet_name=DATA_SHEETS["extra_batter"]),
        }
    except Exception as e:
        st.error(f"데이터 파일 로드 실패: {e}"); return None

def get_safe_index(item_list, target_value):
    try:
        items = [str(x) for x in item_list]
        return items.index(str(target_value)) if str(target_value) in items else 0
    except: return 0

def get_player_pool(data):
    p, b = data["p_p"].copy(), data["p_b"].copy()
    p["구분"], b["구분"] = "투수", "타자"
    res = pd.concat([p, b], ignore_index=True)
    res["label"] = res.apply(lambda x: f"[{str(x['연도'])}] {x['구단']} {x['이름']} ({x['등급']})", axis=1)
    return res

def calculate_saved_result(data, config):
    label = config.get("selected_card_label") or config.get("card_label")
    if not label:
        raise ValueError("저장 파일에 분석 대상 정보가 없습니다. 최신 앱에서 다시 저장해 주세요.")

    players = get_player_pool(data)
    matched = players[players["label"] == label]
    if matched.empty:
        raise ValueError(f"선수 DB에서 저장된 분석 대상을 찾을 수 없습니다: {label}")

    player = matched.iloc[0]
    p_type, p_grade, p_team, base_p = player["구분"], player["등급"], player["구단"], player["POWER"]
    p_cost = int(player.get("코스트", player.get("COST", 0)))
    target_stats = PITCHER_STATS if p_type == "투수" else BATTER_STATS
    skill_db, career_db, ex_db = (data["s_p"], data["c_p"], data["c_ex_p"]) if p_type == "투수" else (data["s_b"], data["c_b"], data["c_ex_b"])

    p_lv = config.get("p_lv", 100)
    c_lv = config.get("c_lv", 100)
    car_lv = config.get("car_lv", 150)
    atl_lv = config.get("atl_lv", 0)
    enh_lv = config.get("enh_lv", 0)
    team_count = config.get("team_count", 1)
    user_team = config.get("user_team_select", p_team)

    cl_bonus = (min(c_lv, 50)*10 + (max(0, c_lv-75))*10) if is_same_team(p_team, user_team) else (min(max(0, c_lv-50), 25)*10 + (max(0, c_lv-75))*10)
    weight_p = base_p + ((p_lv-1)*10) + cl_bonus + (car_lv-1) + (GRADE_CONSTANTS[p_grade]["atlas"]*atl_lv) + (GRADE_CONSTANTS[p_grade]["enhance"]*enh_lv)

    c_slots, opt_counts = [], {}
    for i in range(6):
        opt = config.get(f"o{i}", "미개방")
        amt = config.get(f"a{i}", 0)
        c_slots.append({"옵션": opt, "상승량": amt})
        opt_counts[opt] = opt_counts.get(opt, 0) + 1

    career_p_inc, career_stat_bonus = 0, {s: 0 for s in target_stats}
    for slot in c_slots:
        o_n, b_a, ex_a = slot["옵션"], slot["상승량"], 0
        if o_n != "미개방" and opt_counts[o_n] >= 3:
            match = ex_db[ex_db["옵션"] == o_n]
            if not match.empty: ex_a = match.iloc[0]["상승량"]
        f_a = b_a + ex_a
        if o_n == "동일팀파워": career_p_inc += (f_a * team_count)
        elif o_n == "전체 능력치":
            for st_n in target_stats[:5]: career_stat_bonus[st_n] += f_a
        elif STAT_MAP.get(o_n) in career_stat_bonus: career_stat_bonus[STAT_MAP[o_n]] += f_a

    selected_skills = [config.get("sk1", "없음"), config.get("sk2", "없음"), config.get("sk3", "없음")]
    used_s = [skill_db[skill_db["이름"] == n].iloc[0] for n in selected_skills if n != "없음" and not skill_db[skill_db["이름"] == n].empty]
    p_syn, c_syn, buff = config.get("p_syn", 0), config.get("c_syn", 0), config.get("buff", 0)
    syn_p = int(weight_p * (p_syn / 100)) + c_syn
    sp_sk_p = (32 * team_count) if p_grade in ["ACE", "HIT"] else 0
    sk_p_inc_only = sum([int(weight_p * (sk["파워"]/100)) for sk in used_s if "파워" in sk and pd.notna(sk["파워"])])

    bt_total = 0
    if not (p_grade == "DGN" or p_cost >= 6 or p_cost == 0):
        if p_cost == 5:
            bt_k = "GROUP_1" if p_grade in BT_RARITY_5_DATA["GROUP_1"] else ("GROUP_3" if p_grade in BT_RARITY_5_DATA["GROUP_3"] else "GROUP_2")
            rar_data = BT_RARITY_5_DATA[bt_k + "_VALS"]
        else:
            rar_data = BT_BASE_VALS.get(p_cost, {})
        bt_total = rar_data.get(config.get("bt_lv", 0), 0)

    mid_p_pre = weight_p + syn_p + sp_sk_p + sk_p_inc_only + career_p_inc + buff
    eng_p_total_pct = config.get("eng_p1", 0) + config.get("eng_p2", 0)
    eng_p_bonus = int(mid_p_pre * (eng_p_total_pct / 100))
    mid_p_final = mid_p_pre + eng_p_bonus

    binder_cat_sum = sum(config.get(name, 0) for name in ["b_team", "b_pos", "b_pers", "b_year", "b_grad"])
    clan_lv, binder_lv = config.get("clan_lv", 0), config.get("binder_lv", 0)
    eng_stats = {stat: config.get(f"e1_{stat}", 0) + config.get(f"e2_{stat}", 0) for stat in target_stats}

    dist_each = (mid_p_final - base_p) / 5
    mid_stats = {col: player[col] + (dist_each if i < 5 else 0) for i, col in enumerate(target_stats)}
    final_stats = {}
    for i, col in enumerate(target_stats):
        val = mid_stats[col]
        for sk in used_s:
            if col in sk and pd.notna(sk[col]):
                val += mid_stats[col] * (sk[col] / 100) if not (p_type == "투수" and sk["이름"] == "맞춰잡기" and col == "한계투구") else 10
        val += career_stat_bonus[col] + eng_stats[col]
        if i < 5: val += (clan_lv/5) + binder_lv + (binder_cat_sum/5) + (bt_total/5)
        final_stats[col] = val

    return {
        "label": label,
        "player": player,
        "target_stats": target_stats,
        "final_stats": final_stats,
        "total_power": sum(final_stats.values()),
        "mid_power": mid_p_final,
    }

def render_saved_comparison(data, left_config, right_config):
    left, right = calculate_saved_result(data, left_config), calculate_saved_result(data, right_config)

    st.subheader("🧾 비교 요약")
    summary = pd.DataFrame([
        {"구분": "A", "선수": left["label"], "중간 파워": f"{left['mid_power']:,.0f}", "최종 실전 파워": f"{left['total_power']:,.0f}"},
        {"구분": "B", "선수": right["label"], "중간 파워": f"{right['mid_power']:,.0f}", "최종 실전 파워": f"{right['total_power']:,.0f}"},
    ])
    st.table(summary)

    all_stats = list(dict.fromkeys(left["target_stats"] + right["target_stats"]))
    rows = []
    for stat in all_stats:
        a_val = left["final_stats"].get(stat)
        b_val = right["final_stats"].get(stat)
        rows.append({
            "항목": stat,
            "A": "-" if a_val is None else f"{a_val:,.1f}",
            "B": "-" if b_val is None else f"{b_val:,.1f}",
            "B-A": "-" if a_val is None or b_val is None else f"{b_val-a_val:+,.1f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ==========================================
# 3. 앱 레이아웃 및 설정
# ==========================================
st.set_page_config(page_title="9UP 시뮬 v21.1", layout="wide")
st.markdown("<style>div.row-widget.stRadio > div{flex-direction:row;}</style>", unsafe_allow_html=True)
st.title("⚾ 9UP 프로야구 통합 시뮬레이터 v21.1")

data = load_all_data()

if 'init_21_1' not in st.session_state:
    st.session_state['init_21_1'] = True
    defaults = {'p_lv': 100, 'c_lv': 100, 'car_lv': 150, 'atl_lv': 0, 'enh_lv': 0, 'bt_lv': 0, 'eng_p1': 0, 'eng_p2': 0}
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

if data:
    analysis_tab, compare_tab = st.tabs(["단일 분석", "저장 결과 비교"])
    with analysis_tab:
        with st.sidebar:
            st.header("📂 데이터 관리")
            uploaded = st.file_uploader("JSON 설정 불러오기", type="json")
            if uploaded:
                for k, v in json.load(uploaded).items(): st.session_state[k] = v
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
                choice_idx = get_safe_index(res['label'].tolist(), st.session_state.get('selected_card_label', st.session_state.get('card_label', "")))
                return res[res['label'] == st.selectbox("분석 대상 선택", res['label'].tolist(), index=choice_idx, key="selected_card_label")].iloc[0]
            return None
    
        player = find_player()
    
        if player is not None:
            p_type, p_grade, p_team, base_p = player['구분'], player['등급'], player['구단'], player['POWER']
            p_cost = int(player.get('코스트', player.get('COST', 0))) 
            target_stats = PITCHER_STATS if p_type == '투수' else BATTER_STATS
            graph_labels = P_GRAPH_ORDER if p_type == '투수' else B_GRAPH_ORDER
            skill_db, career_db, ex_db = (data['s_p'], data['c_p'], data['c_ex_p']) if p_type == '투수' else (data['s_b'], data['c_b'], data['c_ex_b'])
    
            st.success(f"🎯 분석 대상: [{str(player['연도'])}] {p_team} {player['이름']} ({p_grade} / {p_cost}코스트)")
            col_in, col_res = st.columns([1.4, 1.1])
    
            with col_in:
                # 1단계: 육성
                with st.expander("🛠️ 1단계: 선수 육성 및 강화", expanded=False):
                    l1, l2, l3 = st.columns(3)
                    p_lv, c_lv, car_lv = l1.number_input("선수레벨", 1, 100, key="p_lv"), l2.number_input("구단레벨", 1, 100, key="c_lv"), l3.number_input("커리어레벨", 1, 150, key="car_lv")
                    atl_lv, max_e = st.slider("도감 단계", 0, 10, key="atl_lv"), (10 if p_grade == "DGN" else 15)
                    if st.session_state.get('enh_lv', 0) > max_e: st.session_state['enh_lv'] = max_e
                    enh_lv = st.slider("강화 단계", 0, max_e, key="enh_lv")
                    cl_bonus = (min(c_lv, 50)*10 + (max(0, c_lv-75))*10) if is_same_team(p_team, user_team) else (min(max(0, c_lv-50), 25)*10 + (max(0, c_lv-75))*10)
                    weight_p = base_p + ((p_lv-1)*10) + cl_bonus + (car_lv-1) + (GRADE_CONSTANTS[p_grade]['atlas']*atl_lv) + (GRADE_CONSTANTS[p_grade]['enhance']*enh_lv)
    
                # 2단계: 커리어 ([수정] 미개방 옵션 추가)
                with st.expander("🧬 2단계: 커리어 슬롯 설정", expanded=False):
                    c_slots, opt_counts = [], {}
                    for i in range(6):
                        st.markdown(f"**📍 슬롯 {i+1}**")
                        g_opts = ["마스터"] if i == 5 else ["루키", "프로", "엘리트", "마스터"]
                        grade = st.radio(f"등급_{i}", g_opts, index=get_safe_index(g_opts, st.session_state.get(f"g{i}", "마스터" if i==5 else "루키")), key=f"g{i}", horizontal=True, label_visibility="collapsed")
                        
                        # 옵션 리스트에 '미개방' 추가
                        db_opts = career_db[career_db['등급'] == grade]['옵션'].unique()
                        opts_with_none = ["미개방"] + list(db_opts)
                        
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
                    
                    career_p_inc, career_stat_bonus = 0, {s: 0 for s in target_stats}
                    for s in c_slots:
                        o_n, b_a, ex_a = s['옵션'], s['상승량'], 0
                        if o_n != "미개방" and opt_counts[o_n] >= 3:
                            match = ex_db[ex_db['옵션'] == o_n]
                            if not match.empty: ex_a = match.iloc[0]['상승량']
                        f_a = b_a + ex_a
                        if o_n == "동일팀파워": career_p_inc += (f_a * team_count)
                        elif o_n == "전체 능력치":
                            for st_n in target_stats[:5]: career_stat_bonus[st_n] += f_a
                        elif STAT_MAP.get(o_n) in career_stat_bonus: career_stat_bonus[STAT_MAP[o_n]] += f_a
    
                # 3단계: 스킬
                with st.expander("🔮 3단계: 스킬 및 시너지 설정", expanded=False):
                    avail_s = ["없음"] + [s.strip() for s in str(player['스킬']).split(',')] if pd.notna(player['스킬']) else ["없음"]
                    sk1, sk2, sk3 = st.selectbox("스킬1", avail_s, key="sk1"), st.selectbox("스킬2", avail_s, key="sk2"), st.selectbox("스킬3", avail_s, key="sk3")
                    used_s = [skill_db[skill_db['이름'] == n].iloc[0] for n in [sk1, sk2, sk3] if n != "없음"]
                    p_syn, c_syn, buff = st.number_input("% 시너지", 0, key="p_syn"), st.number_input("상수 시너지", 0, key="c_syn"), st.number_input("기타 버프", 0, key="buff")
                    syn_p = int(weight_p * (p_syn / 100)) + c_syn
                    sp_sk_p = (32 * team_count) if p_grade in ['ACE', 'HIT','GG'] else 0
                    sk_p_inc_only = sum([int(weight_p * (sk['파워']/100)) for sk in used_s if '파워' in sk and pd.notna(sk['파워'])])
    
                # 4단계: 각인 ([수정] 각인 파워 1, 2 정수화)
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
                with st.expander("🏛️ 5단계: 클랜 및 바인더 설정", expanded=False):
                    bc1, bc2 = st.columns(2)
                    clan_lv, binder_lv = bc1.slider("클랜 레벨", 0, 15, key="clan_lv"), bc2.number_input("바인더 레벨", 0, 100, key="binder_lv")
                    cat_cols, cat_v, b_res = st.columns(5), [0, 10, 17, 22, 25, 27], []
                    for i, name in enumerate(["b_team", "b_pos", "b_pers", "b_year", "b_grad"]):
                        v = cat_cols[i].selectbox(name.split('_')[1], cat_v, key=name); b_res.append(v)
                    binder_cat_sum = sum(b_res)
    
                # 6단계: 돌파
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
                exclude = ['config', 'init_21_1']
                st.download_button("💾 설정 저장 (JSON)", data=json.dumps({k: v for k, v in st.session_state.items() if k not in exclude}, ensure_ascii=False, indent=4), file_name=f"9UP_Save_{player['이름']}_{p_grade}.json", mime="application/json")
    
            # --- [연산 엔진: 보정된 각인 파워 로직] ---
            mid_p_pre = weight_p + syn_p + sp_sk_p + sk_p_inc_only + career_p_inc + buff
            eng_p_total_pct = eng_p1 + eng_p2
            eng_p_bonus = int(mid_p_pre * (eng_p_total_pct / 100))
            mid_p_final = mid_p_pre + eng_p_bonus
            
            dist_each = (mid_p_final - base_p) / 5
            mid_stats = {col: player[col] + (dist_each if i < 5 else 0) for i, col in enumerate(target_stats)}
            final_stats = {}
            for i, col in enumerate(target_stats):
                val = mid_stats[col]
                for sk in used_s:
                    if col in sk and pd.notna(sk[col]): val += mid_stats[col] * (sk[col] / 100) if not (p_type == '투수' and sk['이름'] == '맞춰잡기' and col == '한계투구') else 10
                val += career_stat_bonus[col] + eng_stats[col]
                if i < 5: val += (clan_lv/5) + binder_lv + (binder_cat_sum/5) + (bt_total/5)
                final_stats[col] = val
    
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

    with compare_tab:
        st.header("저장 결과 비교")
        left_file, right_file = st.columns(2)
        with left_file:
            uploaded_a = st.file_uploader("비교 A JSON", type="json", key="compare_a_json")
        with right_file:
            uploaded_b = st.file_uploader("비교 B JSON", type="json", key="compare_b_json")

        if uploaded_a and uploaded_b:
            try:
                config_a = json.load(uploaded_a)
                config_b = json.load(uploaded_b)
                render_saved_comparison(data, config_a, config_b)
            except Exception as e:
                st.error(f"비교 데이터를 불러오지 못했습니다: {e}")
        else:
            st.info("단일 분석 탭에서 각각 설정 저장(JSON)을 만든 뒤, 여기서 두 파일을 불러오면 비교할 수 있습니다.")

import pandas as pd
import streamlit as st
import re
import plotly.graph_objects as go
import json

# ==========================================
# 1. 시스템 상수 및 데이터 정의
# ==========================================
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

TEAM_GROUPS = [
    ["Hanwha", "Binggrae", "한화", "빙그레"], ["SSG", "SK", "에스에스지", "에스케이"],
    ["KIA", "Haitai", "기아", "해태"], ["Doosan", "OB", "두산", "오비"],
    ["Hyundai", "Pacific", "Sammi", "Chungbo", "현대", "태평양", "삼미", "청보"],
    ["LG", "MBC", "엘지", "엠비씨"], ["Kiwoom", "Nexen", "키움", "넥센"]
]

STAT_MAP = {
    "컨택트": "컨택", "삼진 회피": "삼진회피", "홈런 파워": "홈런 파워", 
    "갭 파워": "갭 파워", "선구": "선구", "수비": "수비", "주루": "주루", "도루": "도루",
    "무브먼트": "무브먼트", "장타 억제": "장타 억제", "홈런 억제": "홈런 억제", 
    "컨트롤": "컨트롤", "스터프": "스터프", "한계투구": "한계투구", "주자견제": "주자견제"
}

# ==========================================
# 2. 유틸리티 함수
# ==========================================
def is_same_team(team1, team2):
    t1, t2 = str(team1).strip().lower(), str(team2).strip().lower()
    if t1 == t2: return True
    for group in TEAM_GROUPS:
        if any(name.lower() in t1 for name in group) and any(name.lower() in t2 for name in group):
            return True
    return False

@st.cache_data
def load_all_data():
    try:
        p_db, s_db, c_db = '9UP 프로야구_선수DB_202603_ver.3.xlsx', '9UP 프로야구 스킬 정보.xlsx', '9UP 프로야구 커리어 정보.xlsx'
        return {
            "p_p": pd.read_excel(p_db, sheet_name='투수'), "p_b": pd.read_excel(p_db, sheet_name='타자'),
            "s_p": pd.read_excel(s_db, sheet_name='투수'), "s_b": pd.read_excel(s_db, sheet_name='타자'),
            "c_p": pd.read_excel(c_db, sheet_name='투수'), "c_b": pd.read_excel(c_db, sheet_name='타자'),
            "c_ex_p": pd.read_excel(c_db, sheet_name='추가투수'), "c_ex_b": pd.read_excel(c_db, sheet_name='추가타자')
        }
    except Exception as e:
        st.error(f"데이터 파일 로드 실패: {e}"); return None

def get_safe_index(item_list, target_value):
    try:
        items = [str(x) for x in item_list]
        target = str(target_value)
        return items.index(target) if target in items else 0
    except: return 0

# ==========================================
# 3. 데이터 로드 및 앱 설정
# ==========================================
st.set_page_config(page_title="9UP 시뮬 v13.0", layout="wide")
st.title("⚾ 9UP 프로야구 통합 시뮬레이터 v13.0")

data = load_all_data()

if 'init' not in st.session_state:
    st.session_state['init'] = True
    defaults = {
        'p_lv': 100, 'c_lv': 100, 'car_lv': 150, 'atl_lv': 0, 'enh_lv': 0,
        'p_syn': 0, 'c_syn': 0, 'buff': 0, 'clan_lv': 0, 'binder_lv': 0,
        'team_count': 28, 'player_name_input': ""
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

if data:
    with st.sidebar:
        st.header("📂 데이터 관리")
        uploaded = st.file_uploader("JSON 설정 불러오기", type="json")
        if uploaded:
            loaded_data = json.load(uploaded)
            for k, v in loaded_data.items():
                st.session_state[k] = v
            st.success("데이터 로드 완료!")

        st.divider()
        st.header("🔍 검색 및 팀 설정")
        name_in = st.text_input("선수명", key="player_name_input")
        grade_fil = st.selectbox("등급 필터", ["전체"] + list(GRADE_CONSTANTS.keys()), key="grade_filter")
        user_team = st.selectbox("내 구단 설정", sorted(list(set(data['p_p']['구단'].dropna()))), key="user_team_select")
        team_count = st.number_input("같은 팀원 수 (1~28)", 1, 28, key="team_count")

    def find_player():
        p, b = data['p_p'].copy(), data['p_b'].copy()
        if name_in:
            p, b = p[p['이름'].str.contains(name_in, na=False)], b[b['이름'].str.contains(name_in, na=False)]
        if grade_fil != "전체":
            p, b = p[p['등급'] == grade_fil], b[b['등급'] == grade_fil]
        p['구분'], b['구분'] = '투수', '타자'
        res = pd.concat([p, b], ignore_index=True)
        if len(res) > 0:
            res['label'] = res.apply(lambda x: f"[{str(x['연도'])}] {x['구단']} {x['이름']} ({x['등급']})", axis=1)
            target_label = st.session_state.get('card_label', "")
            choice_idx = get_safe_index(res['label'].tolist(), target_label)
            return res[res['label'] == st.selectbox("분석 대상 선택", res['label'].tolist(), index=choice_idx, key="selected_card_label")].iloc[0]
        return None

    player = find_player()

    if player is not None:
        p_type, p_grade, p_team, base_p = player['구분'], player['등급'], player['구단'], player['POWER']
        target_stats = PITCHER_STATS if p_type == '투수' else BATTER_STATS
        graph_labels = P_GRAPH_ORDER if p_type == '투수' else B_GRAPH_ORDER
        skill_db, career_db, ex_db = (data['s_p'], data['c_p'], data['c_ex_p']) if p_type == '투수' else (data['s_b'], data['c_b'], data['c_ex_b'])

        col_input, col_result = st.columns([1.5, 1])

        with col_input:
            # --- 1단계: 육성 ---
            with st.expander("🛠️ 1단계: 선수 육성 및 강화", expanded=False):
                l1, l2, l3 = st.columns(3)
                p_lv, c_lv, car_lv = l1.number_input("선수레벨", 1, 100, key="p_lv"), l2.number_input("구단레벨", 1, 100, key="c_lv"), l3.number_input("커리어레벨", 1, 150, key="car_lv")
                atl_lv = st.slider("도감 단계", 0, 10, key="atl_lv")
                
                max_enh = 10 if p_grade == "DGN" else 15
                if st.session_state.get('enh_lv', 0) > max_enh: st.session_state['enh_lv'] = max_enh
                enh_lv = st.slider("강화 단계", 0, max_enh, key="enh_lv")
                
                is_mine = is_same_team(p_team, user_team)
                cl_bonus = (min(c_lv, 50)*10 + (max(0, c_lv-75))*10) if is_mine else (min(max(0, c_lv-50), 25)*10 + (max(0, c_lv-75))*10)
                enh_p = ((p_lv-1)*10) + cl_bonus + (car_lv-1) + (GRADE_CONSTANTS[p_grade]['atlas']*atl_lv) + (GRADE_CONSTANTS[p_grade]['enhance']*enh_lv)
                weight_p = base_p + enh_p
                st.info(f"💡 1단계 강화파워 총합: +{enh_p:,.0f}")

            # --- 2단계: 커리어 (세트 효과 로직 보강) ---
            with st.expander("🧬 2단계: 커리어 슬롯 설정", expanded=False):
                c_slots, s_cols = [], st.columns(3)
                for i in range(6):
                    with s_cols[i % 3]:
                        st.markdown(f"**슬롯 {i+1}**")
                        g_opt = ["마스터"] if i == 5 else ["루키", "프로", "엘리트", "마스터"]
                        grade = st.selectbox(f"등급 {i+1}", g_opt, index=get_safe_index(g_opt, st.session_state.get(f"g{i}", "마스터" if i==5 else "루키")), key=f"g{i}")
                        opts = career_db[career_db['등급'] == grade]['옵션'].unique()
                        opt = st.selectbox(f"옵션 {i+1}", opts, index=get_safe_index(opts, st.session_state.get(f"o{i}", opts[0])), key=f"o{i}")
                        vals = career_db[(career_db['등급'] == grade) & (career_db['옵션'] == opt)]['상승량'].tolist()
                        amt = st.selectbox(f"수치 {i+1}", vals, index=get_safe_index(vals, st.session_state.get(f"a{i}", vals[0])), key=f"a{i}")
                        c_slots.append({"옵션": opt, "상승량": amt})

                career_p_inc, career_stat_bonus, opt_counts = 0, {s: 0 for s in target_stats}, {}
                # 1. 옵션별 개수 파악
                for s in c_slots:
                    opt_counts[s['옵션']] = opt_counts.get(s['옵션'], 0) + 1

                # 2. 계산 (개별 슬롯 + 세트 추가 효과)
                for s in c_slots:
                    opt_name = s['옵션']
                    base_amt = s['상승량']
                    
                    # 세트 효과 여부 확인 (해당 옵션이 3개 이상일 때 ex_db 참조)
                    extra_amt = 0
                    if opt_counts[opt_name] >= 3:
                        ex_match = ex_db[ex_db['옵션'] == opt_name]
                        if not ex_match.empty:
                            extra_amt = ex_match.iloc[0]['상승량']
                    
                    # 최종 슬롯당 수치 = 기본 + 추가
                    final_slot_amt = base_amt + extra_amt
                    
                    if opt_name == "동일팀파워":
                        career_p_inc += (final_slot_amt * team_count)
                    elif opt_name == "전체 능력치":
                        for st_name in target_stats[:5]: career_stat_bonus[st_name] += final_slot_amt
                    elif STAT_MAP.get(opt_name) in career_stat_bonus:
                        career_stat_bonus[STAT_MAP[opt_name]] += final_slot_amt

                st.info(f"💡 2단계 커리어파워 기여분: +{career_p_inc + sum(career_stat_bonus.values()):,.0f} (세트효과 포함)")

            # --- 3단계: 스킬 ---
            with st.expander("🔮 3단계: 스킬 및 시너지 설정", expanded=False):
                avail_s = ["없음"] + [s.strip() for s in str(player['스킬']).split(',')] if pd.notna(player['스킬']) else ["없음"]
                sk_cols = st.columns(3)
                sk1 = sk_cols[0].selectbox("스킬1", avail_s, index=get_safe_index(avail_s, st.session_state.get("sk1", "없음")), key="sk1")
                sk2 = sk_cols[1].selectbox("스킬2", avail_s, index=get_safe_index(avail_s, st.session_state.get("sk2", "없음")), key="sk2")
                sk3 = sk_cols[2].selectbox("스킬3", avail_s, index=get_safe_index(avail_s, st.session_state.get("sk3", "없음")), key="sk3")
                used_s = [skill_db[skill_db['이름'] == n].iloc[0] for n in [sk1, sk2, sk3] if n != "없음"]
                b_cols = st.columns(3)
                p_syn, c_syn, buff = b_cols[0].number_input("% 시너지", 0, key="p_syn"), b_cols[1].number_input("상수 시너지", 0, key="c_syn"), b_cols[2].number_input("기타 버프", 0, key="buff")
                syn_p = int(weight_p * (p_syn / 100)) + c_syn
                sp_sk_p = (32 * team_count) if p_grade in ['ACE', 'HIT'] else 0
                sk_p_inc_only = sum([int(weight_p * (sk['파워']/100)) for sk in used_s if '파워' in sk and pd.notna(sk['파워'])])
                st.info(f"💡 3단계 시너지/스킬파워 기여분: +{syn_p + sp_sk_p + sk_p_inc_only + buff:,.0f}")

            # --- 4~5단계: 각인, 클랜/바인더 ---
            with st.expander("💎 4단계: 각인 설정", expanded=False):
                eng_stats = {}
                e_main1, e_main2 = st.columns(2)
                for idx, stat in enumerate(target_stats):
                    with (e_main1 if idx < 4 else e_main2):
                        st.markdown(f"**{stat}**")
                        v1 = st.number_input(f"{stat} S1", 0, key=f"e1_{stat}", label_visibility="collapsed")
                        v2 = st.number_input(f"{stat} S2", 0, key=f"e2_{stat}", label_visibility="collapsed")
                        eng_stats[stat] = v1 + v2

            with st.expander("🏛️ 5단계: 클랜 및 바인더 설정", expanded=False):
                bc1, bc2 = st.columns(2)
                clan_lv, binder_lv = bc1.slider("클랜 레벨", 0, 15, key="clan_lv"), bc2.number_input("바인더 레벨", 0, 100, key="binder_lv")
                cat_cols = st.columns(5)
                cat_v, b_res = [0, 10, 17, 22, 25, 27], []
                for i, name in enumerate(["b_team", "b_pos", "b_pers", "b_year", "b_grad"]):
                    v = cat_cols[i].selectbox(name.split('_')[1], cat_v, key=name)
                    b_res.append(v)
                binder_cat_sum = sum(b_res)
                st.info(f"💡 5단계 클랜/바인더 기여분: +{clan_lv + (binder_lv*5) + binder_cat_sum:,.0f}")

            st.divider()
            exclude = ['config', 'init', 'selected_card_label']
            final_save_json = {k: v for k, v in st.session_state.items() if k not in exclude}
            final_save_json['card_label'] = st.session_state.get('selected_card_label', "")
            st.download_button("💾 현재 설정 완벽 저장 (JSON)", data=json.dumps(final_save_json, ensure_ascii=False, indent=4), file_name=f"9UP_Config_{player['이름']}_{p_grade}.json", mime="application/json")

        # --- 연산 엔진 및 결과 ---
        mid_p = weight_p + syn_p + sp_sk_p + sk_p_inc_only + career_p_inc + buff
        dist_each = (mid_p - base_p) / 5
        mid_stats = {col: player[col] + (dist_each if i < 5 else 0) for i, col in enumerate(target_stats)}
        final_stats = {}
        for i, col in enumerate(target_stats):
            val = mid_stats[col]
            for sk in used_s:
                if col in sk and pd.notna(sk[col]):
                    if p_type == '투수' and sk['이름'] == '맞춰잡기' and col == '한계투구': val += 10
                    else: val += mid_stats[col] * (sk[col] / 100)
            val += career_stat_bonus[col] + eng_stats[col]
            if i < 5: val += (clan_lv / 5) + binder_lv + (binder_cat_sum / 5)
            final_stats[col] = val

        with col_result:
            radar_r = [final_stats[l] for l in graph_labels]
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=radar_r + [radar_r[0]], theta=graph_labels + [graph_labels[0]], fill='toself', fillcolor='rgba(255, 215, 0, 0.4)', line=dict(color='#FFD700', width=4)))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, max(final_stats.values())*1.2]), angularaxis=dict(rotation=90, direction="clockwise")), showlegend=False, height=420)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"""<div style="background-color: #ff9900; padding: 25px; border-radius: 15px; text-align: center; border: 5px solid #cc7700;"><span style="color: white; font-size: 4rem; font-weight: 1000;">{sum(final_stats.values()):,.0f}</span></div>""", unsafe_allow_html=True)
            st.table(pd.DataFrame([{"항목": c, "최종": f"{final_stats[c]:,.1f}", "상승": f"+{final_stats[c]-player[c]:,.1f}"} for c in target_stats]))
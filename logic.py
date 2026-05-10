import re
import pandas as pd
from constants import TEAM_GROUPS, STAT_MAP

def is_same_team(team1, team2):
    t1, t2 = str(team1).strip().lower(), str(team2).strip().lower()
    if t1 == t2: return True
    for group in TEAM_GROUPS:
        in_g1 = any(name.lower() in t1 for name in group)
        in_g2 = any(name.lower() in t2 for name in group)
        if in_g1 and in_g2: return True
    return False

def calculate_power_and_stats(player, inputs, target_stats, skill_db, ex_db):
    # 1. 체급파워
    is_mine = is_same_team(player['구단'], inputs['user_team'])
    c_lv = inputs['c_lv']
    cl_bonus = (min(c_lv, 50)*10 + (max(0, c_lv-75))*10) if is_mine else (min(max(0, c_lv-50), 25)*10 + (max(0, c_lv-75))*10)
    enh_p = ((inputs['p_lv']-1)*10) + cl_bonus + (inputs['car_lv']-1) + (inputs['c_consts']['atlas']*inputs['atl_lv']) + (inputs['c_consts']['enhance']*inputs['enh_lv'])
    weight_p = player['POWER'] + enh_p

    # 2. 커리어/시너지 파워
    career_p_inc, career_stat_bonus, opt_counts = 0, {s: 0 for s in target_stats}, {}
    for s in inputs['c_slots']:
        opt_counts[s['옵션']] = opt_counts.get(s['옵션'], 0) + 1
        if s['옵션'] == "동일팀파워": career_p_inc += (s['상승량'] * inputs['team_count'])
        elif s['옵션'] == "전체 능력치": 
            for st_name in target_stats[:5]: career_stat_bonus[st_name] += s['상승량']
        elif STAT_MAP.get(s['옵션']) in career_stat_bonus: career_stat_bonus[STAT_MAP[s['옵션']]] += s['상승량']

    # 커리어 세트 보너스
    for opt, count in opt_counts.items():
        if count >= 3:
            ex_row = ex_db[ex_db['옵션'] == opt]
            if not ex_row.empty:
                ex_amt = ex_row.iloc[0]['상승량'] * count
                if opt == "동일팀파워": career_p_inc += (ex_amt * inputs['team_count'])
                elif opt == "전체 능력치":
                    for st_name in target_stats[:5]: career_stat_bonus[st_name] += ex_amt
                elif STAT_MAP.get(opt) in career_stat_bonus: career_stat_bonus[STAT_MAP[opt]] += ex_amt

    syn_p = int(weight_p * (inputs['p_syn'] / 100)) + inputs['c_syn']
    sp_sk_p = (32 * inputs['team_count']) if player['등급'] in ['ACE', 'HIT'] else 0
    sk_p_inc = sum([int(weight_p * (sk['파워']/100)) for sk in inputs['used_s'] if '파워' in sk and pd.notna(sk['파워'])])
    
    mid_p = weight_p + syn_p + sp_sk_p + sk_p_inc + career_p_inc + inputs['buff']

    # 3. 최종 스탯 배분 (중간 스탯 기준 스킬 % 적용)
    dist_each = (mid_p - player['POWER']) / 5
    final_stats = {}
    mid_stats = {col: player[col] + (dist_each if i < 5 else 0) for i, col in enumerate(target_stats)}

    for i, col in enumerate(target_stats):
        val = mid_stats[col]
        for sk in inputs['used_s']:
            if col in sk and pd.notna(sk[col]):
                if player['구분'] == '투수' and sk['이름'] == '맞춰잡기' and col == '한계투구': val += 10
                else: val += mid_stats[col] * (sk[col] / 100)
        val += career_stat_bonus[col] + inputs['eng_stats'][col]
        if i < 5: val += (inputs['clan_lv'] / 5) + inputs['binder_lv'] + (inputs['cat_sum'] / 5)
        final_stats[col] = val

    return mid_p, final_stats, mid_stats

def calculate_career_bonuses(c_slots, opt_counts, ex_db, target_stats, team_count):
    career_p_inc = 0
    career_stat_bonus = {s: 0 for s in target_stats}

    for slot in c_slots:
        opt_name, base_amount, extra_amount = slot['옵션'], slot['상승량'], 0
        if opt_name != "미개방" and opt_counts[opt_name] >= 3:
            match = ex_db[ex_db['옵션'] == opt_name]
            if not match.empty:
                extra_amount = match.iloc[0]['상승량']

        final_amount = base_amount + extra_amount
        if opt_name == "동일팀파워":
            career_p_inc += final_amount * team_count
        elif opt_name == "전체 능력치":
            for stat_name in target_stats[:5]:
                career_stat_bonus[stat_name] += final_amount
        elif STAT_MAP.get(opt_name) in career_stat_bonus:
            career_stat_bonus[STAT_MAP[opt_name]] += final_amount

    return career_p_inc, career_stat_bonus

def calculate_final_stats(
    player,
    target_stats,
    used_skills,
    career_stat_bonus,
    eng_stats,
    base_power,
    weight_power,
    syn_power,
    special_skill_power,
    skill_power_bonus,
    career_power_bonus,
    buff,
    engraving_power_pct,
    clan_level,
    binder_level,
    binder_category_sum,
    breakthrough_total,
):
    mid_power_pre = (
        weight_power
        + syn_power
        + special_skill_power
        + skill_power_bonus
        + career_power_bonus
        + buff
    )
    engraving_power_bonus = int(mid_power_pre * (engraving_power_pct / 100))
    mid_power_final = mid_power_pre + engraving_power_bonus

    distributed_each = (mid_power_final - base_power) / 5
    mid_stats = {
        col: player[col] + (distributed_each if index < 5 else 0)
        for index, col in enumerate(target_stats)
    }

    final_stats = {}
    for index, col in enumerate(target_stats):
        value = mid_stats[col]
        for skill in used_skills:
            if col in skill and pd.notna(skill[col]):
                if player['구분'] == '투수' and skill['이름'] == '맞춰잡기' and col == '한계투구':
                    value += 10
                else:
                    value += mid_stats[col] * (skill[col] / 100)

        value += career_stat_bonus[col] + eng_stats[col]
        if index < 5:
            value += (clan_level / 5) + binder_level + (binder_category_sum / 5) + (breakthrough_total / 5)
        final_stats[col] = value

    return {
        "mid_power_pre": mid_power_pre,
        "engraving_power_bonus": engraving_power_bonus,
        "mid_power_final": mid_power_final,
        "mid_stats": mid_stats,
        "final_stats": final_stats,
    }

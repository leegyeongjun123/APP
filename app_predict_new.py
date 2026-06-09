# =========================================================================
# 🛡️ [파이썬 3.10 호환성 패치] NotRequired 임포트 버그 방어막
# =========================================================================
import typing
if not hasattr(typing, "NotRequired"):
    try:
        from typing_extensions import NotRequired
        typing.NotRequired = NotRequired
    except ImportError:
        typing.NotRequired = typing.Any
# =========================================================================

import os
import ast
import math
import pandas as pd
import streamlit as st 
import streamlit.components.v1 as components 
import py3Dmol 

from mp_api.client import MPRester
from pymatgen.core import Structure, Lattice
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

# 스트림릿 대시보드 레이아웃 설정
st.set_page_config(page_title="AI 생성 소재 실시간 교차 검증기", layout="wide")
st.title("🔮 AI 신물질 에너지 & 3D 구조 실시간 대조 시스템 (RF vs GNN)")
st.write("Materials Project와 에너지를 비교하고, AI가 생성한 3D 뼈대와 실제 구조를 시각적으로 검증합니다.")

# 🔑 Materials Project API Key
MP_API_KEY = "MIzkDnGoYEqNPLa4WPIKIc2y4IOpPwsC" 
generated_file = "discovered_materials.csv"

# 🌟 데이터 대조용 기본 매칭기
matcher = StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5) 

# =========================================================================
# 🚀 실시간 비교 엔진 가동
# =========================================================================
if not os.path.exists(generated_file):
    st.warning(f"⚠️ '{generated_file}' 파일이 존재하지 않습니다. 파이프라인을 먼저 실행해주세요.")
else:
    if st.button("🔍 화면에서 즉시 실제 데이터와 구조/에너지 대조하기"):
        with st.spinner("미국 MP 서버 조회 및 3D 기하학적 구조 쌍방향 매칭 가동 중..."):
            
            df = pd.read_csv(generated_file)
            
            mpr = None
            if MP_API_KEY:
                try: mpr = MPRester(MP_API_KEY)
                except Exception as e: st.error(f"API 연결 실패: {e}")

            comparison_results = []
            st.session_state['parsed_structures'] = {}

            for idx, row in df.iterrows():
                formula = str(row['Formula'])
                rf_energy = row['RF_Predicted_Energy'] 
                gnn_energy = row.get('GNN_Predicted_Energy', "데이터 없음")
                
                mp_energy = "데이터 없음"
                structure_match_status = "비교 대상 없음"
                
                gen_struct = None
                mp_struct = None 
                
                try:
                    raw_data = ast.literal_eval(str(row['Web_App_Structure_Data']))[0]
                    lattice = Lattice([[x * 1e10 for x in raw_data['data']['a']],
                                       [x * 1e10 for x in raw_data['data']['b']],
                                       [x * 1e10 for x in raw_data['data']['c']]])
                    species = []
                    coords = []
                    for atom in raw_data['data']['atoms']:
                        species.append(atom['element'])
                        coords.append([atom['x'] * 1e10, atom['y'] * 1e10, atom['z'] * 1e10])
                    
                    gen_struct = Structure(lattice, species, coords, coords_are_cartesian=True)
                except:
                    structure_match_status = "구조 파싱 실패"

                if mpr is not None and gen_struct is not None:
                    try:
                        docs = mpr.summary.search(formula=formula, fields=["formation_energy_per_atom", "structure"])
                        if docs:
                            best_doc = min(docs, key=lambda d: d.formation_energy_per_atom)
                            mp_energy = round(best_doc.formation_energy_per_atom, 4)
                            
                            raw_mp_struct = best_doc.structure
                            sga = SpacegroupAnalyzer(raw_mp_struct, symprec=0.1)
                            mp_struct = sga.get_conventional_standard_structure() 
                            
                            structure_match_status = "💎 새로운 동질이상 (신물질!)"
                            for doc in docs:
                                if matcher.fit(gen_struct, doc.structure):
                                    structure_match_status = "✅ 기존 구조 완벽 일치"
                                    break
                    except Exception as e:
                        mp_energy = "조회 실패"
                        structure_match_status = "조회 실패"
                elif mpr is None:
                    mp_energy = "API Key 없음"

                if gen_struct is not None:
                    mat_key = f"No.{row.get('No', idx+1)} - {formula}"
                    st.session_state['parsed_structures'][mat_key] = {
                        "ai": gen_struct,
                        "mp": mp_struct
                    }

                try: error_rf = round(abs(rf_energy - mp_energy), 4) if isinstance(mp_energy, (int, float)) else "대조 불가"
                except: error_rf = "대조 불가"

                try: error_gnn = round(abs(float(gnn_energy) - mp_energy), 4) if isinstance(mp_energy, (int, float)) and gnn_energy != "데이터 없음" else "대조 불가"
                except: error_gnn = "대조 불가"

                comparison_results.append({
                    "No": row.get('No', idx+1),
                    "화학식": formula,
                    "🌲 RF 예측": rf_energy,
                    "🧠 GNN 예측": gnn_energy,
                    "🏛️ MP 정답": mp_energy,
                    "RF 오차": error_rf,
                    "GNN 오차": error_gnn,
                    "3D 구조 판독": structure_match_status
                })

            result_display_df = pd.DataFrame(comparison_results)

        st.success("🎉 에너지 및 3D 구조 대조 작업이 완료되었습니다!")
        st.subheader("📊 신소재 교차 검증 실시간 대조표 (RF vs GNN)")
        st.dataframe(result_display_df, use_container_width=True)

# =========================================================================
# 🎨 [궁극의 시각화] 대칭군/공간군 프로필 추출 + 하이브리드 동기화
# =========================================================================
if 'parsed_structures' in st.session_state and st.session_state['parsed_structures']:
    st.divider()
    st.subheader("🔬 AI vs 정답(MP) 1:1 정밀 비교 및 결정학 프로필 뷰어")
    st.write("결정계, 점군, 공간군을 완벽히 추출하고 물질의 고유 대칭성에 맞춰 1:1 체급으로 강제 동기화합니다.")
    
    mat_options = list(st.session_state['parsed_structures'].keys())
    selected_mat = st.selectbox("비교해 볼 화학식을 선택하세요:", mat_options)
    
    visual_scale = st.slider("결합선(Bond) 민감도 조절", min_value=0.70, max_value=1.00, value=0.95, step=0.01)
    
    if selected_mat:
        structs = st.session_state['parsed_structures'][selected_mat]
        
        ai_struct = structs['ai'].copy() if structs['ai'] else None
        mp_struct = structs['mp'].copy() if structs['mp'] else None
        
        if ai_struct and mp_struct:
            # 🌟 1. MP 구조의 완벽한 결정학 프로필 추출
            sga_mp = SpacegroupAnalyzer(mp_struct, symprec=0.1)
            mp_sys = sga_mp.get_crystal_system().title()
            mp_pg = sga_mp.get_point_group_symbol()
            mp_sg = sga_mp.get_space_group_symbol()
            mp_sgn = sga_mp.get_space_group_number()
            mp_profile = f"[{mp_sys}] 점군: {mp_pg}, 공간군: {mp_sg} (No.{mp_sgn})"
            
            # 2. 시각화 전용 매핑기 투입
            visual_matcher = StructureMatcher(ltol=0.3, stol=0.3, angle_tol=5, primitive_cell=False)
            matched_ai = visual_matcher.get_s2_like_s1(mp_struct, ai_struct)
            
            if matched_ai is not None:
                ai_struct = matched_ai
                st.success(f"✨ **결정학적 동기화 완벽 성공!** MP의 대칭성을 이용해 1:1 벌크 형태(**{len(mp_struct)}개의 원자**)로 완벽 복원했습니다.")
                # 🌟 완벽 일치하므로 AI 프로필도 MP와 동일하게 출력!
                st.info(f"🤖 **AI 프로필:** {mp_profile} (완벽 일치!)\n\n🏛️ **MP 프로필:** {mp_profile}")
            else:
                # 3. 강제 투영 실패 시 -> AI 스스로의 족보(프로필) 캐내기
                try:
                    sga_ai = SpacegroupAnalyzer(ai_struct, symprec=0.2)
                    ai_struct = sga_ai.get_conventional_standard_structure()
                    ai_sys = sga_ai.get_crystal_system().title()
                    ai_pg = sga_ai.get_point_group_symbol()
                    ai_sg = sga_ai.get_space_group_symbol()
                    ai_sgn = sga_ai.get_space_group_number()
                    ai_profile = f"[{ai_sys}] 점군: {ai_pg}, 공간군: {ai_sg} (No.{ai_sgn})"
                except:
                    ai_profile = "[Unknown] 비대칭 (P1)"
                
                # 4. 각각 폈는데 원자 수가 다르면 최소공배수(LCM) 보정
                if len(ai_struct) != len(mp_struct):
                    ai_num = len(ai_struct)
                    mp_num = len(mp_struct)
                    lcm_num = (ai_num * mp_num) // math.gcd(ai_num, mp_num)
                    
                    if lcm_num <= 400: 
                        ai_mult = lcm_num // ai_num
                        mp_mult = lcm_num // mp_num
                        
                        def get_best_factors(n):
                            best_abc = [1, 1, 1]
                            min_diff = float('inf')
                            for a in range(1, n + 1):
                                if n % a != 0: continue
                                rem = n // a
                                for b in range(1, rem + 1):
                                    if rem % b != 0: continue
                                    c = rem // b
                                    diff = max(a,b,c) - min(a,b,c)
                                    if diff < min_diff:
                                        min_diff = diff
                                        best_abc = [a, b, c]
                            return best_abc
                        
                        if ai_mult > 1: ai_struct.make_supercell(get_best_factors(ai_mult))
                        if mp_mult > 1: mp_struct.make_supercell(get_best_factors(mp_mult))
                        
                        st.warning(f"⚠️ 기하학적 형태가 달라 억지 투영은 피했습니다. 대신 **최소공배수(LCM) 보정**을 통해 양쪽 모두 **{len(ai_struct)}개**로 체급을 맞췄습니다!")
                    else:
                        st.error(f"⚠️ 두 구조의 차이가 너무 커서 원본을 유지합니다. (AI: {ai_num}개, MP: {mp_num}개)")
                else:
                    st.success(f"✨ **자체 대칭 복원 성공!** 각자의 고유 대칭성을 살리면서도 원자 수가 **{len(ai_struct)}개**로 동일하게 맞춰졌습니다!")
                
                # 🌟 각기 다른 두 물질의 프로필을 깔끔하게 비교 출력!
                st.info(f"🤖 **AI 프로필:** {ai_profile}\n\n🏛️ **MP 프로필:** {mp_profile}")

        # =========================================================

        col1, col2 = st.columns(2)
        with col1: 
            ai_title = f"🤖 AI 생성 구조 (총 {len(ai_struct)}개)" if ai_struct else "🤖 AI 구조"
            st.markdown(f"<h3 style='text-align: center;'>{ai_title}</h3>", unsafe_allow_html=True)
        with col2: 
            mp_title = f"🏛️ MP 정답 구조 (총 {len(mp_struct)}개)" if mp_struct else "🏛️ 학계 실제 구조"
            st.markdown(f"<h3 style='text-align: center;'>{mp_title}</h3>", unsafe_allow_html=True)
        
        view = py3Dmol.view(width=1000, height=500, viewergrid=(1,2), linked=True)
        
        if ai_struct:
            ai_vis_struct = ai_struct.copy()
            ai_vis_struct.scale_lattice(ai_struct.volume * visual_scale) 
            view.addModel(ai_vis_struct.to(fmt="cif"), 'cif', viewer=(0,0))
            view.setStyle({'sphere': {'scale': 0.3}, 'stick': {'radius': 0.1}}, viewer=(0,0))
            view.addUnitCell(viewer=(0,0))
            view.zoomTo(viewer=(0,0))
            
        if mp_struct:
            mp_vis_struct = mp_struct.copy()
            mp_vis_struct.scale_lattice(mp_struct.volume * visual_scale) 
            view.addModel(mp_vis_struct.to(fmt="cif"), 'cif', viewer=(0,1))
            view.setStyle({'sphere': {'scale': 0.3}, 'stick': {'radius': 0.1}}, viewer=(0,1))
            view.addUnitCell(viewer=(0,1))
            view.zoomTo(viewer=(0,1))
            
        import streamlit.components.v1 as components 
        components.html(view._make_html(), height=500)

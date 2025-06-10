
# DB SQL문 작성시 유의사항
 - timescale DB를 사용한다.
 - timescale DB의 각종 특성(압축 매커니즘)을 고려한 SQL문을 작성한다.
 - Date()함수 같이 압축된 과거 청크 데이터를 전부 다 해제하는 함수의 사용은 지양한다.

# KA10095, 관심종목정보요청
Header
Element	한글명	type	Required	Length	Description
cont-yn	연속조회여부	String	N	1	다음 데이터가 있을시 Y값 전달
next-key	연속조회키	String	N	50	다음 데이터가 있을시 다음 키값 전달
api-id	TR명	String	Y	10	

-응답 Body
Element	한글명	type	Required	Length	Description
atn_stk_infr	관심종목정보	LIST	N		
- stk_cd	종목코드	String	N	20	
- stk_nm	종목명	String	N	20	
- cur_prc	현재가	String	N	20	
- base_pric	기준가	String	N	20	
- pred_pre	전일대비	String	N	20	
- pred_pre_sig	전일대비기호	String	N	20	
- flu_rt	등락율	String	N	20	
- trde_qty	거래량	String	N	20	
- trde_prica	거래대금	String	N	20	
- cntr_qty	체결량	String	N	20	
- cntr_str	체결강도	String	N	20	
- pred_trde_qty_pre	전일거래량대비	String	N	20	
- sel_bid	매도호가	String	N	20	
- buy_bid	매수호가	String	N	20	
- sel_1th_bid	매도1차호가	String	N	20	
- sel_2th_bid	매도2차호가	String	N	20	
- sel_3th_bid	매도3차호가	String	N	20	
- sel_4th_bid	매도4차호가	String	N	20	
- sel_5th_bid	매도5차호가	String	N	20	
- buy_1th_bid	매수1차호가	String	N	20	
- buy_2th_bid	매수2차호가	String	N	20	
- buy_3th_bid	매수3차호가	String	N	20	
- buy_4th_bid	매수4차호가	String	N	20	
- buy_5th_bid	매수5차호가	String	N	20	
- upl_pric	상한가	String	N	20	
- lst_pric	하한가	String	N	20	
- open_pric	시가	String	N	20	
- high_pric	고가	String	N	20	
- low_pric	저가	String	N	20	
- close_pric	종가	String	N	20	
- cntr_tm	체결시간	String	N	20	
- exp_cntr_pric	예상체결가	String	N	20	
- exp_cntr_qty	예상체결량	String	N	20	
- cap	자본금	String	N	20	
- fav	액면가	String	N	20	
- mac	시가총액	String	N	20	
- stkcnt	주식수	String	N	20	
- bid_tm	호가시간	String	N	20	
- dt	일자	String	N	20	
- pri_sel_req	우선매도잔량	String	N	20	
- pri_buy_req	우선매수잔량	String	N	20	
- pri_sel_cnt	우선매도건수	String	N	20	
- pri_buy_cnt	우선매수건수	String	N	20	
- tot_sel_req	총매도잔량	String	N	20	
- tot_buy_req	총매수잔량	String	N	20	
- tot_sel_cnt	총매도건수	String	N	20	
- tot_buy_cnt	총매수건수	String	N	20	
- prty	패리티	String	N	20	
- gear	기어링	String	N	20	
- pl_qutr	손익분기	String	N	20	
- cap_support	자본지지	String	N	20	
- elwexec_pric	ELW행사가	String	N	20	
- cnvt_rt	전환비율	String	N	20	
- elwexpr_dt	ELW만기일	String	N	20	
- cntr_engg	미결제약정	String	N	20	
- cntr_pred_pre	미결제전일대비	String	N	20	
- theory_pric	이론가	String	N	20	
- innr_vltl	내재변동성	String	N	20	
- delta	델타	String	N	20	
- gam	감마	String	N	20	
- theta	쎄타	String	N	20	
- vega	베가	String	N	20	
- law	로	String	N	20	

# KA10081, 주식일봉차트조회요청
Header
Element	한글명	type	Required	Length	Description
cont-yn	연속조회여부	String	N	1	다음 데이터가 있을시 Y값 전달
next-key	연속조회키	String	N	50	다음 데이터가 있을시 다음 키값 전달
api-id	TR명	String	Y	10	

-응답 Body
Element	한글명	type	Required	Length	Description
stk_cd	종목코드	String	N	6	
stk_dt_pole_chart_qry	주식일봉차트조회	LIST	N		
- cur_prc	현재가	String	N	20	
- trde_qty	거래량	String	N	20	
- trde_prica	거래대금	String	N	20	
- dt	일자	String	N	20	
- open_pric	시가	String	N	20	
- high_pric	고가	String	N	20	
- low_pric	저가	String	N	20	
- upd_stkpc_tp	수정주가구분	String	N	20	1:유상증자, 2:무상증자, 4:배당락, 8:액면분할, 16:액면병합, 32:기업합병, 64:감자, 256:권리락
- upd_rt	수정비율	String	N	20	
- bic_inds_tp	대업종구분	String	N	20	
- sm_inds_tp	소업종구분	String	N	20	
- stk_infr	종목정보	String	N	20	
- upd_stkpc_event	수정주가이벤트	String	N	20	
- pred_close_pric	전일종가	String	N	20	

# ka20006, 업종일봉조회요청
-요청 Body
Element	한글명	type	Required	Length	Description
inds_cd	업종코드	String	Y	3	001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고
base_dt	기준일자	String	Y	8	YYYYMMDD

-응답 Body
Element	한글명	type	Required	Length	Description
inds_cd	업종코드	String	N	20	
inds_dt_pole_qry	업종일봉조회	LIST	N		
- cur_prc	현재가	String	N	20	
- trde_qty	거래량	String	N	20	
- dt	일자	String	N	20	
- open_pric	시가	String	N	20	
- high_pric	고가	String	N	20	
- low_pric	저가	String	N	20	
- trde_prica	거래대금	String	N	20	
- bic_inds_tp	대업종구분	String	N	20	
- sm_inds_tp	소업종구분	String	N	20	
- stk_infr	종목정보	String	N	20	
- pred_close_pric	전일종가	String	N	20	

# KA10059, 종목별투자자기관별요청


-응답 Body
Element	한글명	type	Required	Length	Description
stk_invsr_orgn	종목별투자자기관별	LIST	N		
- dt	일자	String	N	20	
- cur_prc	현재가	String	N	20	
- pre_sig	대비기호	String	N	20	
- pred_pre	전일대비	String	N	20	
- flu_rt	등락율	String	N	20	우측 2자리 소수점자리수
- acc_trde_qty	누적거래량	String	N	20	
- acc_trde_prica	누적거래대금	String	N	20	
- ind_invsr	개인투자자	String	N	20	
- frgnr_invsr	외국인투자자	String	N	20	
- orgn	기관계	String	N	20	
- fnnc_invt	금융투자	String	N	20	
- insrnc	보험	String	N	20	
- invtrt	투신	String	N	20	
- etc_fnnc	기타금융	String	N	20	
- bank	은행	String	N	20	
- penfnd_etc	연기금등	String	N	20	
- samo_fund	사모펀드	String	N	20	
- natn	국가	String	N	20	
- etc_corp	기타법인	String	N	20	
- natfor	내외국인	String	N	20	

# KA10060, 종목별투자자기관별차트요청
-응답 Body
Element	한글명	type	Required	Length	Description
stk_invsr_orgn_chart	종목별투자자기관별차트	LIST	N		
- dt	일자	String	N	20	
- cur_prc	현재가	String	N	20	
- pred_pre	전일대비	String	N	20	
- acc_trde_prica	누적거래대금	String	N	20	
- ind_invsr	개인투자자	String	N	20	
- frgnr_invsr	외국인투자자	String	N	20	
- orgn	기관계	String	N	20	
- fnnc_invt	금융투자	String	N	20	
- insrnc	보험	String	N	20	
- invtrt	투신	String	N	20	
- etc_fnnc	기타금융	String	N	20	
- bank	은행	String	N	20	
- penfnd_etc	연기금등	String	N	20	
- samo_fund	사모펀드	String	N	20	
- natn	국가	String	N	20	
- etc_corp	기타법인	String	N	20	
- natfor	내외국인	String	N	20	
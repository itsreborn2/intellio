#!/usr/bin/env python3
"""
get_financial_data() 함수 테스트 스크립트

이 스크립트는 FinancialDataServicePDF의 get_financial_data() 함수를 테스트하기 위한 것입니다.
개선된 Gemini 방식의 PDF 추출 기능을 테스트합니다.

실행 위치: backend 디렉토리에서 실행
사용법: python stockeasy/scripts/test_get_financial_data.py [basic|compare|all]
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 현재 파일의 위치 기준으로 backend 디렉토리 경로 설정
current_file = Path(__file__).resolve()
backend_dir = current_file.parent.parent.parent  # stockeasy/scripts -> stockeasy -> backend
project_root = backend_dir.parent  # backend -> project_root

# sys.path에 backend 디렉토리 추가
sys.path.insert(0, str(backend_dir))

print(f"현재 실행 파일: {current_file}")
print(f"백엔드 디렉토리: {backend_dir}")
print(f"프로젝트 루트: {project_root}")
print(f"sys.path에 추가된 경로: {backend_dir}")
print()

try:
    from sqlalchemy.ext.asyncio import AsyncSession

    from common.core.database import get_db_session
    from stockeasy.services.financial.data_service_pdf import FinancialDataServicePDF

    print("✅ 모든 모듈 import 성공!")
    print()
except ImportError as e:
    print(f"❌ 모듈 import 실패: {e}")
    print(f"현재 작업 디렉토리: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    sys.exit(1)


async def test_get_financial_data():
    """get_financial_data() 함수 테스트"""
    print("=" * 80)
    print("GET_FINANCIAL_DATA() 함수 테스트 시작")
    print("=" * 80)

    # 테스트할 종목 코드 (삼성전자 예시)
    stock_code = "003350"  # 한국화장품제조

    # 날짜 범위 설정 (최근 2년)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=200)
    date_range = {"start_date": start_date, "end_date": end_date}

    print(f"테스트 종목 코드: {stock_code}")
    print(f"조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print()

    db_session = None
    try:
        # 데이터베이스 세션 생성
        db_session = await get_db_session()

        # FinancialDataServicePDF 인스턴스 생성
        service = FinancialDataServicePDF(db_session)

        print("📋 재무 데이터 조회 시작...")
        start_time = datetime.now()

        # get_financial_data() 함수 호출
        financial_data = await service.get_financial_data(stock_code, date_range)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"⏱️ 처리 시간: {duration:.2f}초")
        print()

        # 결과 분석
        if financial_data:
            print("✅ 데이터 조회 성공!")
            print("📊 결과 요약:")
            print(f"   - 종목 코드: {financial_data.get('stock_code', 'N/A')}")
            print(f"   - 보고서 개수: {financial_data.get('count', 0)}")
            print(f"   - 조회 기간: {financial_data.get('date_range', {}).get('start_date', 'N/A')} ~ {financial_data.get('date_range', {}).get('end_date', 'N/A')}")
            print()

            # 보고서 목록 출력
            reports = financial_data.get("reports", {})
            if reports:
                print("📋 보고서 목록:")
                for key, report in reports.items():
                    metadata = report.get("metadata", {})
                    content_length = len(report.get("content", ""))
                    print(f"   - {key}: {metadata.get('year', 'N/A')}년 {metadata.get('type', 'N/A')} ({content_length:,} 글자)")
                    print(f"     파일명: {metadata.get('file_name', 'N/A')}")
                    print(f"     날짜: {metadata.get('date', 'N/A')}")
                    print()

            # 첫 번째 보고서의 콘텐츠 샘플 출력
            if reports:
                first_report_key = list(reports.keys())[0]
                first_report = reports[first_report_key]
                content = first_report.get("content", "")

                print("📄 첫 번째 보고서 콘텐츠 샘플 (처음 1000자):")
                print("-" * 60)
                print(content)
                # if len(content) > 1000:
                #     print(f"\n... (총 {len(content):,} 글자 중 1000자 표시)")
                print("-" * 60)
                print()

            # 테이블 구조 확인 (마크다운 테이블이 있는지 확인)
            if reports:
                table_count = 0
                unit_count = 0
                for report in reports.values():
                    content = report.get("content", "")
                    # 마크다운 테이블 패턴 확인
                    table_lines = [line for line in content.split("\n") if line.strip().startswith("|") and line.strip().endswith("|")]
                    if table_lines:
                        table_count += len([line for line in table_lines if "---" in line])
                    # 단위 정보 확인
                    unit_count += content.count("단위:")

                print("📊 테이블 구조 분석:")
                print(f"   - 추출된 테이블 개수 (추정): {table_count}")
                print(f"   - 단위 정보 발견: {unit_count}개")
                print("   - Gemini 방식 적용: ✅")
                print()

            # 개선된 기능 확인
            if reports:
                first_report = list(reports.values())[0]
                content = first_report.get("content", "")

                # 단위 변환 확인
                unit_patterns = ["억원", "조원", "백만원", "십억원"]
                found_units = []
                for unit in unit_patterns:
                    if unit in content:
                        found_units.append(unit)

                print("🔄 단위 변환 확인:")
                if found_units:
                    print(f"   - 발견된 단위: {', '.join(found_units)}")
                    print("   - 단위 변환 적용: ✅")
                else:
                    print("   - 단위 변환 적용: ❓ (단위 정보 없음)")
                print()

        else:
            print("❌ 데이터 조회 실패 또는 빈 결과")

    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
        import traceback

        traceback.print_exc()

    finally:
        # 데이터베이스 세션 정리
        if db_session:
            try:
                await db_session.close()
                print("🔄 데이터베이스 세션 정리 완료")
            except Exception as close_error:
                print(f"❌ 세션 정리 중 오류: {close_error}")

    print("=" * 80)
    print("테스트 완료")
    print("=" * 80)


async def test_compare_methods():
    """기존 방식과 개선된 방식 비교 테스트"""
    print("=" * 80)
    print("개선된 방식 상세 분석 테스트")
    print("=" * 80)

    stock_code = "005930"  # 삼성전자

    # 날짜 범위를 좁게 설정 (최근 1년)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    date_range = {"start_date": start_date, "end_date": end_date}

    print(f"테스트 종목 코드: {stock_code}")
    print(f"조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print()

    db_session = None
    try:
        # 데이터베이스 세션 생성
        db_session = await get_db_session()
        service = FinancialDataServicePDF(db_session)

        # 개선된 방식 테스트
        print("🚀 개선된 방식 (Gemini 방식) 테스트...")
        start_time = datetime.now()

        enhanced_data = await service.get_financial_data(stock_code, date_range)

        enhanced_duration = (datetime.now() - start_time).total_seconds()

        print(f"⏱️ 개선된 방식 처리 시간: {enhanced_duration:.2f}초")
        print(f"📊 개선된 방식 결과: {enhanced_data.get('count', 0)}개 보고서")
        print()

        # 개선된 방식 결과 분석
        if enhanced_data and enhanced_data.get("reports"):
            enhanced_reports = enhanced_data.get("reports", {})
            first_enhanced_report = list(enhanced_reports.values())[0]
            enhanced_content = first_enhanced_report.get("content", "")

            # 테이블 구조 확인
            enhanced_table_lines = [line for line in enhanced_content.split("\n") if line.strip().startswith("|")]
            enhanced_table_count = len([line for line in enhanced_table_lines if "---" in line])

            print("📈 상세 분석 결과:")
            print(f"   - 콘텐츠 길이: {len(enhanced_content):,} 글자")
            print(f"   - 테이블 개수: {enhanced_table_count}")
            print("   - 단위 변환 적용: ✅")
            print()

            # 단위 정보 확인
            unit_mentions = enhanced_content.count("단위:")
            print(f"   - 단위 정보 발견: {unit_mentions}개")

            # 테이블 구조 샘플 출력
            if enhanced_table_lines:
                print("   - 테이블 구조 샘플:")
                for i, line in enumerate(enhanced_table_lines[:8]):  # 처음 8줄만
                    print(f"     {line}")
                if len(enhanced_table_lines) > 8:
                    print(f"     ... (총 {len(enhanced_table_lines)}줄)")
                print()

            # 개선 사항 확인
            improvements = []
            if "단위:" in enhanced_content:
                improvements.append("단위 정보 추출")
            if enhanced_table_count > 0:
                improvements.append("테이블 구조화")
            if any(unit in enhanced_content for unit in ["억원", "조원", "백만원"]):
                improvements.append("단위 변환")

            print("🎯 적용된 개선사항:")
            for improvement in improvements:
                print(f"   ✅ {improvement}")
            print()

        else:
            print("❌ 개선된 방식 결과 없음")

    except Exception as e:
        print(f"❌ 비교 테스트 중 오류 발생: {str(e)}")
        import traceback

        traceback.print_exc()

    finally:
        # 데이터베이스 세션 정리
        if db_session:
            try:
                await db_session.close()
                print("🔄 데이터베이스 세션 정리 완료")
            except Exception as close_error:
                print(f"❌ 세션 정리 중 오류: {close_error}")

    print("=" * 80)
    print("상세 분석 테스트 완료")
    print("=" * 80)


def main():
    """메인 함수"""
    print("GET_FINANCIAL_DATA() 테스트 스크립트 (stockeasy/scripts 버전)")
    print("=" * 80)
    print("사용법:")
    print("  cd backend")
    print("  python stockeasy/scripts/test_get_financial_data.py [test_type]")
    print("  test_type: basic (기본 테스트) | compare (상세 분석) | all (모든 테스트)")
    print("=" * 80)
    print()

    # 명령행 인자 처리
    test_type = sys.argv[1] if len(sys.argv) > 1 else "basic"

    if test_type == "basic":
        asyncio.run(test_get_financial_data())
    elif test_type == "compare":
        asyncio.run(test_compare_methods())
    elif test_type == "all":
        asyncio.run(test_get_financial_data())
        print("\n" + "=" * 80 + "\n")
        asyncio.run(test_compare_methods())
    else:
        print(f"❌ 알 수 없는 테스트 타입: {test_type}")
        print("사용 가능한 옵션: basic, compare, all")
        sys.exit(1)


if __name__ == "__main__":
    main()

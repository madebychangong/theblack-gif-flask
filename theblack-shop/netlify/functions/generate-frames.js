const puppeteer = require('puppeteer-core');
const chromium = require('chrome-aws-lambda');
const fs = require('fs').promises;
const path = require('path');

/**
 * Netlify 서버리스 함수: GIF용 4프레임 이미지 생성
 * 
 * 동작 과정:
 * 1. 사용자 텍스트 받기
 * 2. HTML 템플릿 읽기
 * 3. 텍스트 치환하기
 * 4. Puppeteer로 4프레임 캡처
 * 5. Base64 이미지 배열 반환
 */

exports.handler = async (event, context) => {
  // CORS 헤더 설정 (클라이언트에서 접근 가능하게)
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json'
  };

  // OPTIONS 요청 처리 (CORS preflight)
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: ''
    };
  }

  // POST 요청만 허용
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: 'Method Not Allowed' })
    };
  }

  let browser = null;

  try {
    // 1. 요청 데이터 파싱
    const { text } = JSON.parse(event.body);
    
    if (!text || text.trim() === '') {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: '텍스트를 입력해주세요.' })
      };
    }

    console.log('📝 받은 텍스트:', text);

    // 2. HTML 템플릿 읽기
    const templatePath = path.join(process.cwd(), 'templates', 'theblackempty.html');
    let htmlTemplate;
    
    try {
      htmlTemplate = await fs.readFile(templatePath, 'utf8');
      console.log('✅ 템플릿 로딩 성공');
    } catch (error) {
      console.error('❌ 템플릿 로딩 실패:', error);
      return {
        statusCode: 500,
        headers,
        body: JSON.stringify({ error: '템플릿을 찾을 수 없습니다.' })
      };
    }

    // 3. 텍스트 치환 (템플릿의 설명 부분을 사용자 텍스트로 교체)
    const modifiedHtml = htmlTemplate.replace(
      '여기에 가격표가 들어갑니다...',
      text.replace(/\n/g, '<br>')  // 줄바꿈을 <br>로 변환
    );

    console.log('🔄 텍스트 치환 완료');

    // 4. Puppeteer 브라우저 시작
    browser = await puppeteer.launch({
      args: chromium.args,
      defaultViewport: chromium.defaultViewport,
      executablePath: await chromium.executablePath,
      headless: chromium.headless,
      ignoreHTTPSErrors: true,
    });

    const page = await browser.newPage();
    
    // 페이지 크기 설정 (템플릿 크기에 맞춤)
    await page.setViewport({
      width: 720,
      height: 900,
      deviceScaleFactor: 1
    });

    console.log('🌐 브라우저 시작 완료');

    // 5. 각 프레임별로 스크린샷 캡처
    const frames = [];
    
    for (let frameNumber = 1; frameNumber <= 4; frameNumber++) {
      console.log(`📸 프레임 ${frameNumber} 캡처 중...`);
      
      // HTML에 현재 프레임 클래스 적용
      const frameHtml = modifiedHtml.replace(
        'render-target frame-1',
        `render-target frame-${frameNumber}`
      );
      
      // 페이지에 HTML 로드
      await page.setContent(frameHtml, {
        waitUntil: 'networkidle0',  // 모든 리소스 로딩 완료까지 대기
        timeout: 30000
      });
      
      // 폰트와 스타일이 완전히 적용될 때까지 잠시 대기
      await page.waitForTimeout(500);
      
      // render-target 영역만 스크린샷
      const element = await page.$('.render-target');
      const screenshot = await element.screenshot({
        type: 'png',
        encoding: 'base64'
      });
      
      frames.push(`data:image/png;base64,${screenshot}`);
      console.log(`✅ 프레임 ${frameNumber} 완료`);
    }

    console.log('🎉 모든 프레임 캡처 완료');

    // 6. 성공 응답 반환
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        success: true,
        frames: frames,  // Base64 이미지 배열
        frameCount: 4,
        message: '프레임 생성 완료'
      })
    };

  } catch (error) {
    console.error('❌ 프레임 생성 오류:', error);
    
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({
        success: false,
        error: `프레임 생성 실패: ${error.message}`
      })
    };
    
  } finally {
    // 브라우저 정리
    if (browser) {
      await browser.close();
      console.log('🧹 브라우저 정리 완료');
    }
  }
};

/**
 * 사용법:
 * 
 * POST /.netlify/functions/generate-frames
 * Content-Type: application/json
 * 
 * {
 *   "text": "실시간 가격표\n아이템1: 100원\n아이템2: 200원"
 * }
 * 
 * 응답:
 * {
 *   "success": true,
 *   "frames": ["data:image/png;base64,...", ...],
 *   "frameCount": 4,
 *   "message": "프레임 생성 완료"
 * }
 */
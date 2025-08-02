const puppeteer = require('puppeteer-core');
const chromium = require('chrome-aws-lambda');

/**
 * Netlify 서버리스 함수: GIF용 4프레임 이미지 생성
 * 
 * 동작 과정:
 * 1. 사용자 텍스트 받기
 * 2. HTML 템플릿 하드코딩으로 생성
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

    // 2. HTML 템플릿 하드코딩 (수정된 디자인 적용)
    const getTemplate = (userText) => {
      return `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>더블랙샵 GIF 버전</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body {
      background: #000000;
      margin: 0;
      padding: 0;
      font-family: 'Noto Sans KR', Arial, sans-serif;
    }
    
    .render-target {
      width: 720px;
      height: 900px;
      margin: 0;
      background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%);
      color: #ffffff;
      padding: 15px;
      box-sizing: border-box;
      position: relative;
      overflow: hidden;
    }
    
    .shop-title {
      font-size: 55px;
      font-weight: 800;
      text-align: center;
      margin: 2px 0;
      letter-spacing: 2px;
      transition: all 0.3s ease;
    }
    
    /* 제목 자연스러운 그라데이션 흐르는 효과 */
    .frame-1 .shop-title {
      background: linear-gradient(45deg, #ffd700, #ffb347, #ff8c00);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    
    .frame-2 .shop-title {
      background: linear-gradient(90deg, #ffb347, #ff8c00, #ff6347);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    
    .frame-3 .shop-title {
      background: linear-gradient(135deg, #ff8c00, #ff6347, #ff4500);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    
    .frame-4 .shop-title {
      background: linear-gradient(180deg, #ff6347, #ff4500, #ffd700);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    
    .icon {
      display: inline-block;
      margin: 0 10px;
      font-size: 32px;
      transition: all 0.3s ease;
    }
    
    .frame-1 .icon { transform: scale(1.0); }
    .frame-2 .icon { transform: scale(1.05); }
    .frame-3 .icon { transform: scale(1.1); }
    .frame-4 .icon { transform: scale(1.05); }
    
    .shop-subtitle {
      text-align: center;
      font-size: 18px;
      color: #cccccc;
      margin-bottom: 10px;
    }
    
    .subtitle-divider {
      border: none;
      border-top: 1px solid #444444;
      margin: 20px auto;
      width: 80%;
    }
    
    .info-list {
      list-style: none;
      padding: 0;
      margin: 1px 0;
      text-align: center;
    }
    
    .info-list li {
      font-size: 18px;
      margin: 3px 0;
      color: #ffffff;
      text-align: center;
    }
    
    .info-list .icon {
      margin-right: 15px;
      font-size: 24px;
    }
    
    .cta-btn {
      text-align: center;
      font-size: 22px;
      font-weight: 700;
      padding: 15px 1px;
      margin: 15px auto;
      border-radius: 15px;
      transition: all 0.3s ease;
      border: 2px solid transparent;
      max-width: 400px;
    }
    
    /* 오픈채팅 버튼 자연스러운 그라데이션 흐르는 효과 */
    .frame-1 .cta-btn {
      background: linear-gradient(45deg, #4169e1, #6a5acd, #8a2be2);
      border-color: #4169e1;
      box-shadow: 0 0 20px rgba(65, 105, 225, 0.4);
    }
    
    .frame-2 .cta-btn {
      background: linear-gradient(90deg, #6a5acd, #8a2be2, #9370db);
      border-color: #6a5acd;
      box-shadow: 0 0 22px rgba(106, 90, 205, 0.5);
    }
    
    .frame-3 .cta-btn {
      background: linear-gradient(135deg, #8a2be2, #9370db, #ba55d3);
      border-color: #8a2be2;
      box-shadow: 0 0 25px rgba(138, 43, 226, 0.6);
    }
    
    .frame-4 .cta-btn {
      background: linear-gradient(180deg, #9370db, #ba55d3, #4169e1);
      border-color: #9370db;
      box-shadow: 0 0 22px rgba(147, 112, 219, 0.5);
    }
    
    .divider {
      border: none;
      border-top: 2px solid #444444;
      margin: 20px auto;
      width: 90%;
    }
    
    .section-price-title {
      text-align: center;
      font-size: 33px;
      font-weight: 700;
      color: #ffaa00;
      margin: 5px 0;
      transition: all 0.3s ease;
    }
    
    .frame-1 .section-price-title { 
      color: #ffaa00; 
      text-shadow: 0 0 4px rgba(255, 170, 0, 0.7);
    }
    .frame-2 .section-price-title { 
      color: #ff6600; 
      text-shadow: 0 0 2px rgba(255, 102, 0, 0.8);
    }
    .frame-3 .section-price-title { 
      color: #ff0066; 
      text-shadow: 0 0 4px rgba(255, 0, 102, 0.9);
    }
    .frame-4 .section-price-title { 
      color: #ffaa00; 
      text-shadow: 0 0 5px rgba(255, 170, 0, 0.7);
    }
    
    .description {
      text-align: center;
      font-size: 16px;
      color: #aaaaaa;
      margin: 20px 0;
      line-height: 1.6;
      white-space: pre-wrap; /* 줄바꿈과 공백 보존 */
      word-wrap: break-word; /* 긴 단어 자동 줄바꿈 */
    }
    
    /* 추가 서비스 아이콘 깜빡임 효과 */
    .frame-1 .info-list li:nth-child(1) .icon { color: #ff6666; transform: scale(1.1); }
    .frame-2 .info-list li:nth-child(2) .icon { color: #66ff66; transform: scale(1.1); }
    .frame-3 .info-list li:nth-child(3) .icon { color: #6666ff; transform: scale(1.1); }
    .frame-4 .info-list li:nth-child(4) .icon { color: #ffff66; transform: scale(1.1); }
    
    /* 텍스트가 많을 때를 위한 스타일 */
    .description.long-text {
      font-size: 14px;
      max-height: 200px;
      overflow-y: auto;
      padding: 15px;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* 스크롤바 스타일링 */
    .description::-webkit-scrollbar {
      width: 6px;
    }
    
    .description::-webkit-scrollbar-track {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 3px;
    }
    
    .description::-webkit-scrollbar-thumb {
      background: rgba(255, 170, 0, 0.6);
      border-radius: 3px;
    }
    
    .description::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 170, 0, 0.8);
    }
  </style>
</head>
<body>
  <div class="render-target frame-1">
    <div>
      <h1 class="shop-title">
        THE BLACK SHOP
      </h1>
      <div class="shop-subtitle">디아블로4 시즌9 버스 · 대리 · 아이템 전문 거래소</div>
      <hr class="subtitle-divider">
    </div>
    
    <ul class="info-list">
      <li><span class="icon">🦾</span>모든 장비, 아이템, 재료 완비</li>
      <li><span class="icon">🚌</span>버스, 대리, 세팅 풀 지원</li>
      <li><span class="icon">🦸‍♂️</span>경험 많은 전문 기사 상시 대기</li>
      <li><span class="icon">🔥</span>합리적인 실시간 최저가 보장</li>
    </ul>
    
    <div class="cta-btn">
      💬 오픈채팅은 가격표 클릭!
    </div>
    
    <hr class="divider">
    
    <div>
      <h2 class="section-price-title">💰 실시간 가격표</h2>
    </div>
    
    <!-- 이 부분이 사용자 텍스트로 치환됩니다 -->
    <div class="description">
      ${userText}
    </div>
  </div>
</body>
</html>`;
    };

    console.log('✅ 템플릿 생성 완료');

    // 3. 텍스트 치환 (줄바꿈을 <br>로 변환)
    const modifiedHtml = getTemplate(text.replace(/\n/g, '<br>'));

    console.log('🔄 텍스트 치환 완료');

    // 4. Puppeteer 브라우저 시작 (Netlify Functions 최적화)
    browser = await puppeteer.launch({
      args: [
        ...chromium.args,
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--no-first-run',
        '--no-zygote',
        '--single-process',
        '--disable-gpu'
      ],
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

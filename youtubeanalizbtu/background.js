const API_ENDPOINT = "http://127.0.0.1:5000/analyze_youtube";

// Videoların analiz durumlarını burada tutacağız
// Örnek: { "Wx3m781y_EQ": { status: "loading" veya "done", data: {...} } }
let analysisCache = {}; 

function extractVideoId(url) {
    const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    return match ? match[1] : null;
}

function startAnalysis(url, videoId) {
    // Eğer bu video zaten analiz ediliyorsa veya edildiyse tekrar başlatma!
    if (analysisCache[videoId]) return;

    console.log("🎬 Arka planda analiz başlatılıyor:", videoId);
    analysisCache[videoId] = { status: 'loading' };

    fetch(API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ youtube_link: url })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || `Hata: ${response.status}`); });
        }
        return response.json();
    })
    .then(data => {
        console.log("✅ Analiz tamamlandı:", data);
        analysisCache[videoId] = { status: 'done', data: data }; // Sonucu kaydet
    })
    .catch(error => {
        console.error("❌ Analiz hatası:", error);
        analysisCache[videoId] = { status: 'error', error: error.message };
    });
}

// Tarayıcıda bir sekmeye girildiğinde çalışır
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && tab.url.includes('youtube.com/watch')) {
        const videoId = extractVideoId(tab.url);
        if (videoId) {
            startAnalysis(tab.url, videoId);
        }
    }
});

// Popup açıldığında arka plandan durum bilgisini ister
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "CHECK_STATUS") {
        const videoId = extractVideoId(request.url);
        if (videoId) {
            // Popup açıldığında arka plan uyuyorsa (veya kaçırdıysa) biz başlatalım
            if (!analysisCache[videoId]) {
                startAnalysis(request.url, videoId);
            }
            // Popup'a mevcut durumu (loading, done, error) gönderiyoruz
            sendResponse(analysisCache[videoId]);
        } else {
            sendResponse({ status: 'not_youtube' });
        }
    }
    return true; // Asenkron cevap vereceğimizi belirtiyoruz
});
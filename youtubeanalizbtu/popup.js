document.addEventListener('DOMContentLoaded', () => {
    const STATUS_ELEMENT = document.getElementById('status');
    const CIRCLE_DISPLAY = document.getElementById('circle-display');
    const CIRCLE_TEXT = document.getElementById('circle-text');

    STATUS_ELEMENT.textContent = "Bağlantı kontrol ediliyor...";

    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        const currentUrl = tabs[0].url;

        if (!currentUrl || !currentUrl.includes('youtube.com/watch')) {
            STATUS_ELEMENT.textContent = "❌ Lütfen bir YouTube video sayfasında olduğunuzdan emin olun.";
            STATUS_ELEMENT.className = "error";
            return;
        }

        // Yuvarlağı dönme moduna alıyoruz
        if (CIRCLE_DISPLAY && CIRCLE_TEXT) {
            CIRCLE_DISPLAY.style.display = "flex";
            CIRCLE_DISPLAY.className = "circle loading";
            CIRCLE_TEXT.style.display = "none";
        }
        STATUS_ELEMENT.textContent = "⏳ Video arka planda analiz ediliyor...";

        // Arka plana 1.5 saniyede bir "Analiz Bitti Mi?" diye soran döngü
        const checkInterval = setInterval(() => {
            chrome.runtime.sendMessage({ type: "CHECK_STATUS", url: currentUrl }, (response) => {
                if (!response) return;

                if (response.status === 'done') {
                    clearInterval(checkInterval); // Bitti! Sormayı bırak.
                    showResult(response.data);
                } else if (response.status === 'error') {
                    clearInterval(checkInterval); // Hata oldu! Sormayı bırak.
                    showError(response.error);
                }
                // status === 'loading' ise hiçbir şey yapma, yuvarlak dönmeye devam etsin.
            });
        }, 1500);

    });

    function showResult(data) {
        if (data.status === "no_caption") {
            STATUS_ELEMENT.textContent = `⚠️ Altyazı bulunamadı.`;
            STATUS_ELEMENT.className = "error";
            if (CIRCLE_DISPLAY) CIRCLE_DISPLAY.style.display = "none";
            return;
        }

        const ageRating = data.age_rating;

        if (CIRCLE_DISPLAY && CIRCLE_TEXT) {
            CIRCLE_DISPLAY.className = "circle";
            CIRCLE_TEXT.style.display = "block";
            CIRCLE_TEXT.textContent = ageRating;

            // Renklendirme
            if (ageRating === "+18") CIRCLE_DISPLAY.classList.add("age-18");
            else if (ageRating === "+15") CIRCLE_DISPLAY.classList.add("age-15");
            else if (ageRating === "+13") CIRCLE_DISPLAY.classList.add("age-13");
            else if (ageRating === "+9") CIRCLE_DISPLAY.classList.add("age-9");
            else CIRCLE_DISPLAY.classList.add("age-all");
        }

        STATUS_ELEMENT.textContent = "✅ Analiz Tamamlandı!";
        STATUS_ELEMENT.className = "success";
    }

    function showError(msg) {
        STATUS_ELEMENT.textContent = `❌ Hata: ${msg}`;
        STATUS_ELEMENT.className = "error";
        if (CIRCLE_DISPLAY) CIRCLE_DISPLAY.style.display = "none";
    }
});
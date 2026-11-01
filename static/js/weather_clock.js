/**
 * TIGER AI - REAL-TIME CLOCK & LIVE DEVICE WEATHER WIDGET
 * Tự động cập nhật đồng hồ nhảy từng giây và lấy thời tiết theo vị trí GPS thực tế của thiết bị
 */

(function () {
  const WMO_WEATHER_MAP = {
    0: { desc: "Trời quang", icon: "☀️" },
    1: { desc: "Chủ yếu quang", icon: "🌤️" },
    2: { desc: "Ít mây", icon: "⛅" },
    3: { desc: "Nhiều mây", icon: "☁️" },
    45: { desc: "Có sương mù", icon: "🌫️" },
    48: { desc: "Sương mù giá", icon: "🌫️" },
    51: { desc: "Mưa phùn nhẹ", icon: "🌦️" },
    53: { desc: "Mưa phùn vừa", icon: "🌦️" },
    55: { desc: "Mưa phùn dày", icon: "🌧️" },
    61: { desc: "Mưa rào nhẹ", icon: "🌦️" },
    63: { desc: "Mưa vừa", icon: "🌧️" },
    65: { desc: "Mưa to", icon: "🌧️" },
    80: { desc: "Mưa rải rác", icon: "🌦️" },
    81: { desc: "Mưa rào", icon: "🌧️" },
    82: { desc: "Mưa rào rất to", icon: "⛈️" },
    95: { desc: "Dông sét rải rác", icon: "⛈️" },
    96: { desc: "Dông kèm mưa đá", icon: "⛈️" },
    99: { desc: "Dông bão dữ dội", icon: "⛈️" }
  };

  const DAYS_OF_WEEK_VN = [
    "Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"
  ];

  let lastLat = null;
  let lastLon = null;
  let isFetchingWeather = false;

  // 1. CẬP NHẬT ĐỒNG HỒ THỜI GIAN THỰC (MỖI GIÂY)
  function updateClock() {
    const timeEl = document.getElementById("hwcTime");
    const dateEl = document.getElementById("hwcDate");
    if (!timeEl || !dateEl) return;

    const now = new Date();
    const hours = String(now.getHours()).padStart(2, "0");
    const minutes = String(now.getMinutes()).padStart(2, "0");
    const seconds = String(now.getSeconds()).padStart(2, "0");
    timeEl.textContent = `${hours}:${minutes}:${seconds}`;

    const dayName = DAYS_OF_WEEK_VN[now.getDay()];
    const date = String(now.getDate()).padStart(2, "0");
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const year = now.getFullYear();
    dateEl.textContent = `${dayName}, ${date}/${month}/${year}`;
  }

  // 2. LẤY THỜI TIẾT VÀ TÊN ĐỊA DANH TỪ TỌA ĐỘ GPS
  async function fetchWeatherForCoords(lat, lon) {
    if (isFetchingWeather) return;
    isFetchingWeather = true;

    const locEl = document.getElementById("hwcLocation");
    const iconEl = document.getElementById("hwcWeatherIcon");
    const tempEl = document.getElementById("hwcTemperature");
    const descEl = document.getElementById("hwcWeatherDesc");
    const widgetEl = document.getElementById("headerWeatherClockWidget");

    try {
      // Gọi song song: Reverse Geocoding (Lấy tên địa danh) + Open-Meteo (Thời tiết)
      const geoPromise = fetch(
        `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=vi`
      ).then(r => r.json()).catch(() => null);

      const weatherPromise = fetch(
        `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,weather_code,is_day`
      ).then(r => r.json()).catch(() => null);

      const [geoData, weatherData] = await Promise.all([geoPromise, weatherPromise]);

      // Xử lý Tên địa điểm thiết bị
      let locationName = "Cần Thơ";
      if (geoData) {
        const locality = geoData.locality || geoData.district || geoData.principalSubdivisionDistrict || "";
        const city = geoData.city || geoData.principalSubdivision || "";
        if (locality && city && locality !== city) {
          locationName = `${locality}, ${city}`;
        } else if (city) {
          locationName = city;
        } else if (locality) {
          locationName = locality;
        }
      }

      if (locEl) {
        locEl.textContent = locationName;
        locEl.title = `Tọa độ GPS: ${lat.toFixed(4)}, ${lon.toFixed(4)} (${locationName})`;
      }

      // Xử lý Thời tiết thực tế
      if (weatherData && weatherData.current) {
        const cur = weatherData.current;
        const temp = Math.round(cur.temperature_2m);
        const wCode = cur.weather_code;
        const weatherInfo = WMO_WEATHER_MAP[wCode] || { desc: "Thời tiết ổn định", icon: cur.is_day ? "🌤️" : "🌙" };

        if (tempEl) tempEl.textContent = `${temp}°C`;
        if (iconEl) iconEl.textContent = weatherInfo.icon;
        if (descEl) descEl.textContent = weatherInfo.desc;

        if (widgetEl) {
          widgetEl.title = `📍 ${locationName}\n🌡️ Nhiệt độ: ${temp}°C\n💧 Độ ẩm: ${cur.relative_humidity_2m}%\n🌤️ Tình trạng: ${weatherInfo.desc}\n(Nhấp chuột để làm mới định vị GPS)`;
        }
      }

      lastLat = lat;
      lastLon = lon;
    } catch (e) {
      console.warn("[Weather Widget Error]", e);
      if (descEl && !descEl.textContent) descEl.textContent = "Cập nhật sau";
    } finally {
      isFetchingWeather = false;
    }
  }

  // 3. FALLBACK THEO IP INTERNET (NẾU CHƯA CÓ QUYỀN GPS HOẶC THIẾT BỊ KHÔNG CÓ GPS)
  async function fallbackIpWeather() {
    try {
      const res = await fetch("https://ipapi.co/json/", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.latitude && data.longitude) {
          fetchWeatherForCoords(data.latitude, data.longitude);
          return;
        }
      }
    } catch (e) {
      // Ignored
    }
    // Mặc định Cần Thơ (Trung tâm MT01)
    fetchWeatherForCoords(10.0452, 105.7469);
  }

  // 4. KÍCH HOẠT ĐỊNH VỊ THIẾT BỊ (HTML5 GEOLOCATION API)
  function initDeviceLocation() {
    const locEl = document.getElementById("hwcLocation");
    if (locEl && (!lastLat || !lastLon)) {
      locEl.textContent = "Đang dò GPS...";
    }

    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          fetchWeatherForCoords(lat, lon);
        },
        (err) => {
          console.log("[Geolocation Notice] Dùng IP fallback:", err.message);
          fallbackIpWeather();
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
      );

      // Theo dõi vị trí khi thiết bị di chuyển (Live Tracking)
      try {
        navigator.geolocation.watchPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            // Chỉ cập nhật khi vị trí thay đổi đáng kể (> 0.01 độ ~ 1km)
            if (!lastLat || !lastLon || Math.abs(lat - lastLat) > 0.01 || Math.abs(lon - lastLon) > 0.01) {
              fetchWeatherForCoords(lat, lon);
            }
          },
          null,
          { enableHighAccuracy: false, maximumAge: 300000 }
        );
      } catch (e) {
        // Watch not supported
      }
    } else {
      fallbackIpWeather();
    }
  }

  // Khởi động khi tải xong trang
  function init() {
    updateClock();
    setInterval(updateClock, 1000);

    initDeviceLocation();

    // Tự động làm mới thời tiết mỗi 15 phút
    setInterval(() => {
      if (lastLat && lastLon) {
        fetchWeatherForCoords(lastLat, lastLon);
      } else {
        initDeviceLocation();
      }
    }, 15 * 60 * 1000);

    // Cho phép người dùng nhấp vào widget để ép làm mới định vị
    const widget = document.getElementById("headerWeatherClockWidget");
    if (widget) {
      widget.addEventListener("click", () => {
        const iconEl = document.getElementById("hwcWeatherIcon");
        if (iconEl) {
          iconEl.style.transition = "transform 0.5s ease";
          iconEl.style.transform = "rotate(360deg)";
          setTimeout(() => { iconEl.style.transform = "none"; }, 500);
        }
        initDeviceLocation();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

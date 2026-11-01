/**
 * TIGER AI - REAL-TIME CLOCK & LIVE GOOGLE MAPS WEATHER WIDGET
 * Cập nhật đồng hồ thời gian thực và thời tiết theo tọa độ GPS thiết bị & Cụm Kho MT01
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

  const PRESET_LOCATIONS = {
    cairang: {
      id: "cairang",
      name: "Kho Cái Răng",
      fullName: "Kho Hàng Nặng Cái Răng",
      lat: 10.0078565,
      lon: 105.7968827,
      gmap: "https://maps.app.goo.gl/P9uhaYrMCpTUT3no6"
    },
    binhthuy: {
      id: "binhthuy",
      name: "Kho Bình Thủy",
      fullName: "Kho Hàng Nặng Bình Thủy",
      lat: 10.0078565,
      lon: 105.7968827,
      gmap: "https://maps.app.goo.gl/P9uhaYrMCpTUT3no6"
    },
    omon: {
      id: "omon",
      name: "Kho Ô Môn",
      fullName: "Kho Hàng Nặng Ô Môn",
      lat: 10.153378,
      lon: 105.569997,
      gmap: "https://maps.app.goo.gl/J23y4FKvWKSMZzWZ7"
    },
    vithanh: {
      id: "vithanh",
      name: "Kho Vị Thanh",
      fullName: "Kho Hàng Nặng Vị Thanh",
      lat: 9.7782506,
      lon: 105.4878618,
      gmap: "https://maps.app.goo.gl/c6QiAyEWAkurJ3uL8"
    }
  };

  const FALLBACK_DEFAULT = {
    lat: 10.0078565,
    lon: 105.7968827,
    name: "Cái Răng, Cần Thơ",
    gmap: "https://maps.app.goo.gl/P9uhaYrMCpTUT3no6"
  };

  const STORAGE_KEY = "tiger_selected_location_id";
  let currentLocationId = "device_gps";
  let currentLat = FALLBACK_DEFAULT.lat;
  let currentLon = FALLBACK_DEFAULT.lon;
  let currentGmapUrl = FALLBACK_DEFAULT.gmap;
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

  // 2. CẬP NHẬT LIÊN KẾT GOOGLE MAPS TRÊN GIAO DIỆN
  function updateGoogleMapsLinks(url, locName) {
    currentGmapUrl = url;
    const gmapLink = document.getElementById("hwcGmapLink");
    const ddGmapBtn = document.getElementById("hwcBtnOpenGmap");

    if (gmapLink) {
      gmapLink.href = url;
      gmapLink.title = `Xem ${locName} trên Google Maps (vệ tinh)`;
    }
    if (ddGmapBtn) {
      ddGmapBtn.href = url;
      ddGmapBtn.textContent = `🗺️ Mở "${locName}" trên Google Maps`;
    }
  }

  // 3. LẤY THỜI TIẾT TỪ OPEN-METEO THEO TỌA ĐỘ
  async function fetchWeatherForCoords(lat, lon, customName = null, gmapUrl = null) {
    if (isFetchingWeather) return;
    isFetchingWeather = true;

    const locEl = document.getElementById("hwcLocation");
    const iconEl = document.getElementById("hwcWeatherIcon");
    const tempEl = document.getElementById("hwcTemperature");
    const descEl = document.getElementById("hwcWeatherDesc");
    const widgetEl = document.getElementById("headerWeatherClockWidget");

    try {
      let displayName = customName;
      if (!displayName) {
        try {
          const geoRes = await fetch(
            `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=vi`
          );
          if (geoRes.ok) {
            const geoData = await geoRes.json();
            const locality = geoData.locality || geoData.district || "";
            const city = geoData.city || geoData.principalSubdivision || "";
            if (locality && city && locality !== city) {
              displayName = `${locality}, ${city}`;
            } else {
              displayName = locality || city || "Cần Thơ";
            }
          }
        } catch (e) {
          displayName = "Vị trí GPS";
        }
      }

      if (locEl) {
        locEl.textContent = displayName;
        locEl.title = `Tọa độ: ${lat.toFixed(4)}, ${lon.toFixed(4)} (${displayName})`;
      }

      const finalGmapUrl = gmapUrl || `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
      updateGoogleMapsLinks(finalGmapUrl, displayName);

      const weatherRes = await fetch(
        `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,weather_code,is_day`
      );

      if (weatherRes.ok) {
        const weatherData = await weatherRes.json();
        if (weatherData && weatherData.current) {
          const cur = weatherData.current;
          const temp = Math.round(cur.temperature_2m);
          const wCode = cur.weather_code;
          const weatherInfo = WMO_WEATHER_MAP[wCode] || { desc: "Thời tiết ổn định", icon: cur.is_day ? "🌤️" : "🌙" };

          if (tempEl) tempEl.textContent = `${temp}°C`;
          if (iconEl) iconEl.textContent = weatherInfo.icon;
          if (descEl) descEl.textContent = weatherInfo.desc;

          if (widgetEl) {
            widgetEl.title = `📍 ${displayName}\n🌡️ Nhiệt độ: ${temp}°C\n💧 Độ ẩm: ${cur.relative_humidity_2m}%\n🌤️ Tình trạng: ${weatherInfo.desc}\n(Nhấp chuột để chọn vị trí hoặc mở Google Maps)`;
          }
        }
      }

      currentLat = lat;
      currentLon = lon;
    } catch (e) {
      console.warn("[Weather Widget Error]", e);
      if (descEl && !descEl.textContent) descEl.textContent = "Cập nhật sau";
    } finally {
      isFetchingWeather = false;
    }
  }

  // 4. FALLBACK IP KHI KHÔNG CÓ QUYỀN GPS
  async function fallbackIpWeather() {
    try {
      const res = await fetch("https://ipapi.co/json/", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.latitude && data.longitude) {
          const locName = data.city ? `${data.city}, Cần Thơ` : "Cần Thơ";
          fetchWeatherForCoords(data.latitude, data.longitude, locName, `https://www.google.com/maps/search/?api=1&query=${data.latitude},${data.longitude}`);
          return;
        }
      }
    } catch (e) {
      // Ignored
    }
    fetchWeatherForCoords(FALLBACK_DEFAULT.lat, FALLBACK_DEFAULT.lon, FALLBACK_DEFAULT.name, FALLBACK_DEFAULT.gmap);
  }

  // 5. CHUYỂN ĐỔI ĐỊA ĐIỂM
  function setLocation(locationId) {
    currentLocationId = locationId;
    localStorage.setItem(STORAGE_KEY, locationId);

    // Cập nhật class active trong dropdown
    document.querySelectorAll(".hwc-dd-item").forEach(item => {
      if (item.dataset.id === locationId) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    if (locationId === "device_gps") {
      const locEl = document.getElementById("hwcLocation");
      if (locEl) locEl.textContent = "Đang dò GPS...";

      if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            fetchWeatherForCoords(lat, lon, null, `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`);
          },
          (err) => {
            console.warn("[GPS error, fallback to IP/Default]", err.message);
            fallbackIpWeather();
          },
          { enableHighAccuracy: true, timeout: 8000 }
        );
      } else {
        fallbackIpWeather();
      }
    } else if (PRESET_LOCATIONS[locationId]) {
      const target = PRESET_LOCATIONS[locationId];
      fetchWeatherForCoords(target.lat, target.lon, target.name, target.gmap);
    }
  }

  // 6. KHỞI TẠO SỰ KIỆN GIAO DIỆN VÀ DROPDOWN
  function initEvents() {
    const weatherSection = document.getElementById("hwcWeatherSection");
    const dropdown = document.getElementById("hwcLocationDropdown");
    const closeBtn = document.getElementById("hwcDdClose");
    const gmapLink = document.getElementById("hwcGmapLink");

    if (gmapLink) {
      gmapLink.addEventListener("click", (e) => {
        e.stopPropagation();
      });
    }

    if (weatherSection && dropdown) {
      weatherSection.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = dropdown.style.display === "block";
        dropdown.style.display = isOpen ? "none" : "block";
      });
    }

    if (closeBtn && dropdown) {
      closeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        dropdown.style.display = "none";
      });
    }

    document.querySelectorAll(".hwc-dd-item").forEach(item => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const locId = item.dataset.id;
        if (locId) {
          setLocation(locId);
          if (dropdown) dropdown.style.display = "none";
        }
      });
    });

    document.addEventListener("click", (e) => {
      if (dropdown && dropdown.style.display === "block") {
        if (!dropdown.contains(e.target) && !weatherSection.contains(e.target)) {
          dropdown.style.display = "none";
        }
      }
    });
  }

  // Khởi động khi tải xong trang
  function init() {
    updateClock();
    setInterval(updateClock, 1000);

    initEvents();

    // Mặc định là GPS thiết bị thực tế, dọn dẹp giá trị cũ nếu có
    let savedLoc = localStorage.getItem(STORAGE_KEY) || "device_gps";
    if (savedLoc === "home") {
      savedLoc = "device_gps";
      localStorage.setItem(STORAGE_KEY, "device_gps");
    }
    setLocation(savedLoc);

    // Tự động làm mới thời tiết mỗi 15 phút
    setInterval(() => {
      if (currentLocationId === "device_gps") {
        setLocation("device_gps");
      } else if (PRESET_LOCATIONS[currentLocationId]) {
        const target = PRESET_LOCATIONS[currentLocationId];
        fetchWeatherForCoords(target.lat, target.lon, target.name, target.gmap);
      }
    }, 15 * 60 * 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

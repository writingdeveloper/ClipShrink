// 스켈레톤: 자산 서버 경유 GIF 렌더 검증 프로브 (T6에서 전체 교체)
window.__onShow = () => {};
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && window.pywebview) pywebview.api.hide();
});

async function loadProbe() {
  if (!window.pywebview) return;
  const url = await pywebview.api.probe_url();
  if (url) {
    document.getElementById("probe-img").src = url;
    document.getElementById("probe").textContent = "probe:";
  }
}
if (window.pywebview) loadProbe();
else window.addEventListener("pywebviewready", loadProbe);

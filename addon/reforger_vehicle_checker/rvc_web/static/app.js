const ids = ["addon_root","asset_name","output_directory","source_blend","imported_xob_resource","external_wheel_prefab","template","legacy_alias"];
const report = document.querySelector("#report");
function num(id, def) {
  const el = document.querySelector("#"+id);
  const v = el ? parseFloat(el.value) : NaN;
  return Number.isFinite(v) ? v : def;
}
function chk(id, def) {
  const el = document.querySelector("#"+id);
  return el ? el.checked : def;
}
function payload() {
  const p = Object.fromEntries(ids.map(id => [id, document.querySelector("#"+id).value]));
  p.features = {
    doors: chk("feat_doors", true),
    glass: chk("feat_glass", true),
    lights: chk("feat_lights", true),
    emergency_lights: chk("feat_emergency_lights", false),
    animations: chk("feat_animations", true),
  };
  p.measurements = {
    wheelbase: num("wheelbase", 3.0),
    wheel_radius: num("wheel_radius", 0.4),
    track: num("track", 2.0),
    body_height: num("body_height", 1.8),
    mass: num("mass", 1800),
  };
  return p;
}
async function call(path) {
  report.textContent = "Working...";
  const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload())});
  report.textContent = JSON.stringify(await response.json(), null, 2);
}
document.querySelector("#check").onclick = () => call("/api/check");
document.querySelector("#generate").onclick = () => call("/api/generate");
fetch("/api/status").then(r=>r.json()).then(s=>{
  document.querySelector("#status").textContent = `Blender MCP ${s.blender_mcp ? "connected" : "offline"} | local-only`;
  document.querySelector("#addon_root").value = s.addons_root;
});

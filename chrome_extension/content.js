(function(){
  let badge=null;
  function show(){
    if(badge||document.getElementById("__pm__")) return;
    badge=document.createElement("div"); badge.id="__pm__";
    badge.title="Proxy Monitor active"; badge.textContent="ð¡";
    badge.style.cssText="position:fixed;bottom:16px;right:16px;width:32px;height:32px;border-radius:50%;background:rgba(37,99,235,.9);color:#fff;font-size:16px;display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:2147483647;box-shadow:0 2px 8px rgba(0,0,0,.4)";
    badge.onclick=()=>chrome.storage.local.get(["appUrl"],({appUrl})=>window.open(appUrl||"http://localhost:8081","_blank"));
    document.body.appendChild(badge);
  }
  function hide(){if(badge){badge.remove();badge=null;}}
  function check(){
    chrome.runtime.sendMessage({type:"PROXY_MONITOR_ACTION",path:"/status",method:"GET"},r=>{
      if(chrome.runtime.lastError) return;
      r?.ok&&r.data?.proxy_running ? show() : hide();
    });
  }
  document.body ? check() : document.addEventListener("DOMContentLoaded",check);
  setInterval(check,10000);
})();
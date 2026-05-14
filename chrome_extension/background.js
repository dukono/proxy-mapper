chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({id:"open-pm",title:"Open Proxy Monitor",contexts:["link","page"]});
  chrome.contextMenus.create({id:"mock-url",title:"Create mapping for this URL",contexts:["link"]});
});
chrome.contextMenus.onClicked.addListener(async (info) => {
  const {appUrl} = await chrome.storage.local.get(["appUrl"]);
  const base = appUrl||"http://localhost:8081";
  if (info.menuItemId==="open-pm") { chrome.tabs.create({url:base}); return; }
  try {
    const u = new URL(info.linkUrl);
    await fetch(base+"/api/mappings/create_from_url",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({method:"GET",path:u.pathname,query:Object.fromEntries(u.searchParams),host:u.hostname})});
    chrome.tabs.create({url:base});
  } catch(e) { console.error(e); }
});
chrome.runtime.onMessage.addListener((msg,sender,sendResponse) => {
  if (msg.type==="PROXY_MONITOR_ACTION") {
    chrome.storage.local.get(["appUrl"]).then(({appUrl}) => {
      fetch((appUrl||"http://localhost:8081")+"/api"+msg.path,
        {method:msg.method||"GET",headers:{"Content-Type":"application/json"},body:msg.body?JSON.stringify(msg.body):undefined})
        .then(r=>r.json()).then(d=>sendResponse({ok:true,data:d})).catch(e=>sendResponse({ok:false,error:e.message}));
    });
    return true;
  }
});
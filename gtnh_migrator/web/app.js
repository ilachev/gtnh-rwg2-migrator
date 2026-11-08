'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="migration-token"]').content;
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let lang = localStorage.getItem('language') || (navigator.language.startsWith('ru') ? 'ru' : 'en');
let state = {}, current = 0, wasBusy = false, selectedCandidate = 0, browseTarget = '', folder = {}, mapBox = null;
let selectionDirty = false, sourceDirty = false;
const en = {};
document.querySelectorAll('[data-t]').forEach(el => en[el.dataset.t] = el.innerHTML);
const ru = {
 local:'Работает на вашем компьютере', hero:'Сохраните базы.<br>Откройте новый мир.', intro:'Перейдите на генерацию RWG2, сохранив важные места в вашем мире.',
 copyNote:'Каждая миграция создаёт отдельную копию и проверенный бэкап. Исходный сервер остаётся на месте.', warranty:'Проект сообщества · Без гарантий',
 step1:'01 / ИСХОДНЫЙ МИР',step2:'02 / СОХРАНЕНИЕ',step3:'03 / ГЕНЕРАЦИЯ',step4:'04 / НОВАЯ КОПИЯ',
 sourceTitle:'Начнём с вашего сервера',sourceHelp:'Выберите остановленный сервер GTNH 2.9.0 с установленным RWG2. Мастер работает с локальными папками, в том числе со скачанной копией удалённого сервера.',
 serverFolder:'Папка сервера',clientFolder:'Папка клиента <span class="muted">(необязательно)</span>',browse:'Обзор…',serverHint:'Папка, в которой лежат server.properties, mods и config.',
 clientHint:'Инстанс Prism или папка .minecraft. Позволяет учесть метки и создать подходящую копию клиента.',upgrading:'Переходите с GTNH 2.8.x?',upgradeHelp:'Сначала обновите полную копию мира до 2.9.0 по официальному гайду и проверьте её в игре. Этот мастер выполняет следующий этап — перенос ландшафта на RWG2.',guide:'Официальный гайд по обновлению ↗',noUpload:'Мир никуда не загружается. Аккаунт не нужен.',inspect:'Прочитать мир →',
 preserveTitle:'Какие места оставляем?',preserveHelp:'Каждая область — группа соседних заклеймленных чанков. Выберите базы и добавьте запас вокруг. Все остальные измерения сохраняются целиком.',selectAll:'Выбрать все',selectNone:'Снять выбор',padding:'Запас',chunks:'чанк(а)',waypointsTitle:'Ещё сохранить места возле меток',dimensionsTitle:'Все остальные измерения остаются целиком',dimensionsHelp:'Ад, Сумеречный лес, планеты и прогресс игроков копируются без изменения ландшафта.',back:'← Назад',preparePlan:'Посмотреть границы →',
 estimate:'Расчёт ландшафта без запуска игры',generationTitle:'Подберём подходящий ландшафт',generationHelp:'Смещения RWG2 помогают разместить базы в подходящих биомах и уменьшить стены на границах. Они не сглаживают существующий рельеф автоматически.',fitMap:'Весь мир',kept:'Сохранённые чанки',blocks:'блоков',firstRun:'Первый подбор занимает больше времени',buildHelp:'Нужны Git и JDK 21. Мастер скачает официальный исходный код RWG2 2.0.6 и зависимости сборки, затем выполнит расчёт на вашем компьютере. Обычно это несколько минут; время зависит и от сети.',candidateLabel:'Вариант генерации',sampleHelp:'Перепады оценены в точках вдоль границы. Покрытие биомом тоже выборочное: возможны реки и небольшие соседние биомы. Хорошая оценка не гарантирует полностью незаметных стыков.',calculate:'Подобрать варианты генерации',review:'Проверить и создать копию →',
 originalKept:'Оригинал сохраняется',reviewTitle:'Проверим будущий мир',newServer:'Новая папка сервера',parentFolder:'Выбрать родительскую…',newFolderHint:'Эта папка ещё не должна существовать. Мастер откажется перезаписывать существующую папку.',newClient:'Новая папка клиента',stopped:'Исходный сервер остановлен, клиент Minecraft закрыт. Игроки вышли из игры на сохраняемой территории.',backupTitle:'Полный бэкап мира входит в копию',backupHelp:'Перед изменением ландшафта мастер создаст архив мира. Затем проверит содержимое архива, сохранённых чанков и остальных файлов мира.',createCopy:'Создать проверенную копию',ready:'КОПИЯ ГОТОВА',doneTitle:'Новый мир готов к проверке',doneHelp:'Исходный сервер доступен для возврата. Проверьте новый вариант в игре, прежде чем сделать его основным.',next1:'Запустите новый сервер через start-rwg2-trial.sh (macOS/Linux) или start-rwg2-trial.bat (Windows), используя Java 21.',next2:'Если сервер запускает системная служба или ежедневное задание, укажите в них новую папку и новый скрипт запуска. Существующие службы мастер не меняет автоматически.',next3:'Откройте новый профиль клиента и подключитесь через Multiplayer. Проверьте базы, приваты, инвентарь, квесты и остальные измерения.',rollbackHelp:'Для возврата остановите новый сервер и запустите исходный. Прогресс, сделанный в пробной копии, хранится отдельно.',chooseFolder:'Выберите папку',go:'Перейти',up:'↑ На уровень выше',useFolder:'Выбрать эту папку'
};
const words = {
 en:{steps:['Source world','Keep your places','Find generation','Create a copy','Ready to explore'],kept:'Chunks preserved',reset:'Chunks regenerated',samples:'Boundary samples',average:'Average seam',max:'Largest seam',coverage:'Biome coverage',area:'Area',chunkCount:'chunks',biome:'Biome around this area (optional)',any:'Any biome · prioritize terrain',noClaims:'No overworld claims found. Add a client and select waypoints, or claim your bases in Server Utilities first.',noWaypoints:'No matching overworld waypoints found in the selected client.',other:'All other dimensions, inventories, quests, and claim records stay intact.',chosen:'Selected generation',border:'Border',players:'Players saved outside the preserved area: ',playerHelp:'Return these players to a base on the original server, stop it, and read the world again. Their positions are not changed automatically.',working:'Working on your computer…',failure:'Could not complete this step. Details: ',server:'New server',client:'New client',backup:'Verified world backup',verify:'Unchanged world files outside terrain',option:'Option',noTarget:'No biome preference',seam:'maximum seam',loading:'Reading folders…'},
 ru:{steps:['Исходный мир','Сохранение баз','Подбор генерации','Создание копии','Можно исследовать'],kept:'Чанков сохраняется',reset:'Чанков заново',samples:'Точек на границе',average:'Средний перепад',max:'Максимальный перепад',coverage:'Покрытие биомом',area:'Область',chunkCount:'чанков',biome:'Биом вокруг этой области (необязательно)',any:'Любой биом · важнее ровный стык',noClaims:'Приваты в обычном мире не найдены. Укажите клиент и выберите метки или сначала заклеймите базы через Server Utilities.',noWaypoints:'Метки обычного мира для этого сервера в выбранном клиенте не найдены.',other:'Другие измерения, инвентари, квесты и записи приватов остаются целиком.',chosen:'Выбранный вариант',border:'Запас',players:'За границей сохранения находятся игроки: ',playerHelp:'Верните этих игроков на базу на исходном сервере, остановите его и заново прочитайте мир. Их позиции мастер автоматически не меняет.',working:'Выполняется на вашем компьютере…',failure:'Не удалось завершить этот шаг. Подробности: ',server:'Новый сервер',client:'Новый клиент',backup:'Проверенный бэкап мира',verify:'Неизменённых файлов мира вне ландшафта',option:'Вариант',noTarget:'Без предпочтений по биому',seam:'максимальный перепад',loading:'Читаю папки…'}
};
const w = key => words[lang][key];
const phases = {
 'Starting':'Подготовка',
 'Reading original boundary terrain':'Читаю исходный рельеф на границах',
 'Downloading the official RWG2 2.0.6 source':'Скачиваю официальный исходный код RWG2 2.0.6',
 'Building the offline generator; the first run downloads build dependencies':'Собираю генератор; при первом запуске загружаются зависимости',
 'Searching biome placements':'Ищу подходящее расположение биомов',
 'Comparing boundary terrain':'Сравниваю перепады на границах',
 'Refining selected placements':'Уточняю смещения подходящих вариантов',
 'Checking full boundary samples':'Проверяю все выбранные точки границы',
 'Search complete':'Подбор завершён',
 'Hashing the original world':'Вычисляю хеши исходного мира',
 'Copying the server into a new folder':'Копирую сервер в новую папку',
 'Creating and verifying a complete world backup':'Создаю и проверяю полный бэкап мира',
 'Preserving selected chunks and verifying their compressed records':'Сохраняю выбранные чанки и проверяю их содержимое',
 'Verifying other dimensions, player data, claims, and quests':'Проверяю остальные измерения, игроков, приваты и квесты',
 'Creating a separate client and refreshing only its overworld maps':'Создаю отдельный клиент и обновляю карту обычного мира',
 'Verified copy is ready':'Проверенная копия готова'
};
function translate(){
 document.documentElement.lang=lang;
 document.querySelectorAll('[data-t]').forEach(el=>el.innerHTML=(lang==='ru'?ru:en)[el.dataset.t] || en[el.dataset.t]);
 $('language').textContent=lang==='ru'?'EN':'RU';renderSteps();
}
function showError(error){$('error').textContent=w('failure')+error;$('error').hidden=false;}
async function api(path,data){
 const res=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Migration-Token':token},body:data===undefined?undefined:JSON.stringify(data)});
 const value=await res.json();if(!res.ok)throw new Error(value.error||res.statusText);return value;
}
async function act(path,data){
 $('error').hidden=true;try{await api(path,data);if(['inspect','plan','search','apply'].includes(path))wasBusy=true;await poll();}catch(e){showError(e.message);}
}
function renderSteps(){
 const max=sourceDirty?0:selectionDirty?1:state.result?4:state.fit?3:state.plan?2:state.info?1:0;
 $('steps').innerHTML=w('steps').map((name,i)=>`<button class="${i===current?'active':i<max?'complete':''}" data-step="${i}" ${i>max||state.job?.busy?'disabled':''}><span>${i<max?'✓':i+1}</span>${esc(name)}</button>`).join('');
 $('steps').querySelectorAll('button').forEach(button=>button.onclick=()=>setStep(Number(button.dataset.step)));
}
function setStep(index){
 current=index;for(let i=0;i<5;i++)$('step'+i).hidden=i!==index;
 if(index===1)renderGroups();if(index===2)renderGeneration();if(index===3)renderReview();if(index===4)renderResult();renderSteps();
}
function selection(){
 const biomes={};document.querySelectorAll('.group').forEach(row=>biomes[row.dataset.id]=row.querySelector('[data-biome]').value.trim());
 return {groups:Array.from(document.querySelectorAll('[data-group]:checked'),x=>x.dataset.group),
 waypoints:Array.from(document.querySelectorAll('[data-waypoint]:checked'),x=>x.dataset.waypoint),padding:Number($('padding').value),biomes};
}
let savedSelection=null;
function renderGroups(){
 if(!state.info)return;const sel=savedSelection || state.plan?.selection;
 $('world-name').textContent=state.info.world_name;
 $('groups').innerHTML=state.info.groups.length?state.info.groups.map((g,i)=>`<div class="group" data-id="${esc(g.id)}"><input id="area-${i}" type="checkbox" data-group="${esc(g.id)}" ${!sel||sel.groups.includes(g.id)?'checked':''}><div><label for="area-${i}">${esc(g.team)} · ${w('area')} ${i+1}<small>${g.count} ${w('chunkCount')}</small></label><div class="group-meta">X ${g.bounds[0]*16}…${g.bounds[2]*16+15} · Z ${g.bounds[1]*16}…${g.bounds[3]*16+15}</div><input type="text" list="biomes" data-biome value="${esc(sel?.biomes?.[g.id]||'')}" aria-label="${w('biome')}" placeholder="${w('any')}"></div></div>`).join(''):`<p class="muted">${w('noClaims')}</p>`;
 const list=document.createElement('datalist');list.id='biomes';['Chaparral','Prairie','Shrubland','Coniferous Forest','Meadow','Woodland','Savanna','Temperate Rainforest'].forEach(name=>{const o=document.createElement('option');o.value=name;list.append(o);});$('groups').append(list);
 $('waypoints').innerHTML=state.info.waypoints.length?state.info.waypoints.map((wp,i)=>`<label><input type="checkbox" data-waypoint="${esc(wp.id)}" ${!sel||sel.waypoints.includes(wp.id)?'checked':''}>${esc(wp.name)} <small>(${wp.x}, ${wp.z})</small></label>`).join(''):`<p class="muted">${w('noWaypoints')}</p>`;
 if(sel)$('padding').value=sel.padding;
 document.querySelectorAll('[data-group],[data-biome],[data-waypoint]').forEach(input=>input.onchange=()=>{savedSelection=selection();selectionDirty=true;renderSteps();});
}
function stats(id,values){$(id).innerHTML=values.map(([value,label])=>`<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join('');}
function renderGeneration(){
 if(!state.plan)return;const plan=state.plan;stats('plan-stats',[[plan.retained_chunks.toLocaleString(),w('kept')],[plan.regenerate_chunks.toLocaleString(),w('reset')],[plan.survey.length,w('samples')]]);
 $('candidates').hidden=!state.fit;$('review').hidden=!state.fit;$('search-intro').hidden=!!state.fit;$('search').hidden=!!state.fit;
 if(state.fit){
 $('candidate').innerHTML=state.fit.candidates.map((c,i)=>`<option value="${i}">${w('option')} ${i+1} · ${w('seam')} ${c.max.toFixed(0)} · ${plan.targets.length?w('coverage').toLowerCase()+' '+(c.coverage*100).toFixed(0)+'%':w('noTarget')}</option>`).join('');
 $('candidate').value=selectedCandidate;
 const c=state.fit.candidates[selectedCandidate];stats('fit-stats',[[c.mean.toFixed(1),w('average')],[c.max.toFixed(0),w('max')],[plan.targets.length?(c.coverage*100).toFixed(0)+'%':'—',w('coverage')]]);
 }drawMap();
}
function drawMap(){
 if(!state.plan)return;const p=state.plan;let minX=Infinity,minZ=Infinity,maxX=-Infinity,maxZ=-Infinity;
 p.keep.forEach(([x,z])=>{minX=Math.min(minX,x*16);minZ=Math.min(minZ,z*16);maxX=Math.max(maxX,(x+1)*16);maxZ=Math.max(maxZ,(z+1)*16);});
 const margin=Math.max(48,(maxX-minX)*.06,(maxZ-minZ)*.06);mapBox=[minX-margin,minZ-margin,maxX-minX+2*margin,maxZ-minZ+2*margin];
 const svg=$('map');svg.setAttribute('viewBox',mapBox.join(' '));
 const stride=Math.max(1,Math.ceil(p.keep.length/20000));
 let content=p.keep.filter((_,i)=>i%stride===0).map(([x,z])=>`<rect x="${x*16}" y="${z*16}" width="16" height="16" fill="#b9ced7" stroke="#f2f6f0" stroke-width=".5"/>`).join('');
 const c=state.fit?.candidates[selectedCandidate];
 if(c)content+=p.survey.map(([x,z,old],i)=>{const e=Math.abs(c.heights[i]-old);const color=e<=4?'#3c9666':e<=12?'#c4ac42':e<=24?'#d9803b':'#be5153';return `<circle cx="${x}" cy="${z}" r="2.5" fill="${color}"><title>X ${x}, Z ${z}: ${e} ${w('blocks')||''}</title></circle>`;}).join('');
 svg.innerHTML=content;
}
function renderReview(){
 const p=state.plan,c=p.candidate;$('review-summary').innerHTML=`<strong>${p.retained_chunks} ${esc(w('chunkCount'))} · ${p.regenerate_chunks} → RWG2</strong><span>${esc(w('other'))}</span><span>${esc(w('chosen'))}: ${esc(c.offsets.join(', '))} · ${esc(w('seam'))}: ${c.max}</span>`;
 if(!$('target').value)$('target').value=state.info.server+'-rwg2-trial';
 $('client-target-row').hidden=!state.info.client;if(state.info.client&&!$('client-target').value)$('client-target').value=state.info.client+' RWG2 Trial';
 $('outside-players').hidden=!p.outside_players.length;
 $('outside-players').textContent=w('players')+p.outside_players.map(x=>x.id+' ('+x.position.map(v=>Math.round(v)).join(', ')+')').join('; ')+'\n'+w('playerHelp');
 $('apply').disabled=!$('stopped').checked;
}
function renderResult(){
 const r=state.result;if(!r)return;
 $('result').innerHTML=[[w('server'),r.server],[w('client'),r.client],[w('backup'),r.backup]].filter(x=>x[1]).map(([k,v])=>`<div><strong>${esc(k)}</strong><code>${esc(v)}</code></div>`).join('')+`<div>${esc(w('verify'))}: <b>${r.unchanged_other_world_files}</b></div>`;
}
async function poll(){
 try{
  const next=await api('state');const finished=wasBusy&&!next.job.busy;state=next;
  $('job').hidden=!state.job.busy;$('job-title').textContent=w('working');$('job-message').textContent=lang==='ru'?(phases[state.job.message]||state.job.message):state.job.message;
  document.querySelectorAll('button,input,select').forEach(el=>{if(!el.closest('dialog')&&el.id!=='language')el.disabled=state.job.busy;});
  if(!state.job.busy)$('apply').disabled=!$('stopped').checked;
  if(finished){
   if(state.job.error)showError(state.job.error);
   else if(state.job.kind==='inspect'){sourceDirty=false;selectionDirty=false;savedSelection=null;selectedCandidate=0;$('target').value='';$('client-target').value='';setStep(1);}
   else if(state.job.kind==='plan'){selectionDirty=false;selectedCandidate=0;setStep(2);}
   else if(state.job.kind==='search'){selectedCandidate=0;setStep(2);}
   else if(state.job.kind==='apply')setStep(4);
  }
  wasBusy=state.job.busy;renderSteps();
 }catch(e){showError(e.message);}
}
$('language').onclick=()=>{if(current===1)savedSelection=selection();lang=lang==='ru'?'en':'ru';localStorage.setItem('language',lang);translate();setStep(current);};
$('inspect').onclick=()=>act('inspect',{server:$('server').value.trim(),client:$('client').value.trim()});
$('plan').onclick=()=>{savedSelection=selection();act('plan',savedSelection);};
$('search').onclick=()=>act('search',{});
$('candidate').onchange=async()=>{selectedCandidate=Number($('candidate').value);await act('candidate',{index:selectedCandidate});renderGeneration();};
$('review').onclick=()=>setStep(3);
$('stopped').onchange=()=>{$('apply').disabled=!$('stopped').checked;};
$('apply').onclick=()=>act('apply',{target:$('target').value.trim(),client_target:state.info.client?$('client-target').value.trim():'',stopped:$('stopped').checked});
document.querySelectorAll('.back').forEach(button=>button.onclick=()=>{if(current===1)savedSelection=selection();setStep(Math.max(0,current-1));});
$('all').onclick=()=>{document.querySelectorAll('[data-group]').forEach(x=>x.checked=true);savedSelection=selection();selectionDirty=true;renderSteps();};
$('none').onclick=()=>{document.querySelectorAll('[data-group]').forEach(x=>x.checked=false);savedSelection=selection();selectionDirty=true;renderSteps();};
$('padding').onchange=()=>{savedSelection=selection();selectionDirty=true;renderSteps();};
['server','client'].forEach(id=>$(id).oninput=()=>{sourceDirty=true;renderSteps();});
async function browse(path){
 try{folder=await api('browse',{path});$('browse-path').value=folder.path;$('folder-list').innerHTML=folder.folders.map((p,i)=>`<button data-folder="${i}">▱ &nbsp; ${esc(p.name)}</button>`).join('');$('folder-list').querySelectorAll('button').forEach(b=>b.onclick=()=>browse(folder.folders[Number(b.dataset.folder)].path));}
 catch(e){showError(e.message);}
}
document.querySelectorAll('[data-browse]').forEach(button=>button.onclick=()=>{browseTarget=button.dataset.browse;let path=$(browseTarget).value;if(browseTarget==='target'||browseTarget==='client-target')path=path.replace(/[\\/][^\\/]*$/,'');browse(path);$('browser').showModal();});
$('browse-go').onclick=()=>browse($('browse-path').value);$('browse-path').onkeydown=e=>{if(e.key==='Enter')browse($('browse-path').value);};
$('browse-up').onclick=()=>browse(folder.parent);$('close-browser').onclick=()=>$('browser').close();
$('browse-select').onclick=()=>{let path=folder.path;if(browseTarget==='target')path+='/GTNH-RWG2-Trial';if(browseTarget==='client-target')path+='/GTNH-RWG2-Client';$(browseTarget).value=path;if(['server','client'].includes(browseTarget)){sourceDirty=true;renderSteps();}$('browser').close();};
function zoom(factor){const svg=$('map'),box=svg.getAttribute('viewBox').split(' ').map(Number);box[0]+=box[2]*(1-factor)/2;box[1]+=box[3]*(1-factor)/2;box[2]*=factor;box[3]*=factor;svg.setAttribute('viewBox',box.join(' '));}
$('zoom-in').onclick=()=>zoom(.7);$('zoom-out').onclick=()=>zoom(1.4);$('zoom-reset').onclick=()=>{if(mapBox)$('map').setAttribute('viewBox',mapBox.join(' '));};
let drag=null;$('map').onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,box:$('map').getAttribute('viewBox').split(' ').map(Number)};$('map').setPointerCapture(e.pointerId);};
$('map').onpointermove=e=>{if(!drag)return;const svg=$('map'),rect=svg.getBoundingClientRect(),b=drag.box;const scale=Math.max(b[2]/rect.width,b[3]/rect.height);svg.setAttribute('viewBox',[b[0]-(e.clientX-drag.x)*scale,b[1]-(e.clientY-drag.y)*scale,b[2],b[3]].join(' '));};
$('map').onpointerup=() => drag=null;$('map').onpointercancel=()=>drag=null;
translate();
api('state').then(value=>{state=value;wasBusy=!!state.job.busy;if(state.info){$('server').value=state.info.server;$('client').value=state.info.client;}if(state.fit&&state.plan?.candidate)selectedCandidate=Math.max(0,state.fit.candidates.findIndex(c=>JSON.stringify(c.offsets)===JSON.stringify(state.plan.candidate.offsets)));setStep(state.result?4:state.fit?2:state.plan?2:state.info?1:0);poll();}).catch(e=>showError(e.message));
setInterval(poll,1000);

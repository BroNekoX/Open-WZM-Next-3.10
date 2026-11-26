"""v22 = v21 harness + the useful upstream (lab 3.10 v39) changes.

Base: work/cn/lab_startup_v21.js   (v14 + our channel + stream-off, all guarded)
Out : work/cn/lab_startup_v22.js

Ported from the 2026-11-25 upstream package (new/WZM_warzone.apks):
  * equipment save de-duplication (upstream v38/v39): the tracker re-pushes the
    same ~700 records every 1.5 s; without it every push rewrites the JSON file,
    including while a map loads.
  * saved match options across restarts (mode/map/mpMode/squad/difficulty/
    third-person/radar/player counts) -> ProjectWZMSavedSettings.
  * all-unlock for local loot + Chinese language-pack trigger + score/time
    limits, as one cached Lua prelude.
  * lab_extra.lua override read once, not once per bridge tick.
  * hot-path fix: the per-open native path probe is disabled (the game opens
    thousands of files per second; path matching on every open was pure cost).

Deliberately NOT ported (would trade stability for nothing):
  * removed try/catch around the feature installs, bare dvar reads without the
    mapped-pointer guard, unconditional read/close hooking, the 3 s delayed
    register poke (dsha-nm9), the Java refresh-rate block (this gadget has no
    Java bridge), and per-tick request-file polling that nothing can write.
"""
import io
import json
import os
import sys

SRC = 'work/cn/lab_startup_v21.js'
DST = 'work/cn/lab_startup_v22.js'


class Lines:
    def __init__(self, text):
        self.l = text.split('\n')

    def find(self, needle, start=0):
        hits = [i for i in range(start, len(self.l)) if self.l[i].strip() == needle.strip()]
        assert len(hits) == 1, 'anchor %r -> %d hits' % (needle[:70], len(hits))
        return hits[0]

    def insert(self, at, block, indent=0):
        self.l[at:at] = [(' ' * indent + x) if x else '' for x in block.strip('\n').split('\n')]

    def replace(self, at, block, indent=0):
        del self.l[at]
        self.insert(at, block, indent)

    def text(self):
        return '\n'.join(self.l)


def sub1(text, old, new, label):
    assert text.count(old) == 1, '%s: %d occurrences' % (label, text.count(old))
    return text.replace(old, new)


t = Lines(open(SRC, encoding='utf-8').read())

# 1. equipment de-duplication ------------------------------------------------
i = t.find('globalThis.labSaveEquipment=function(raw){')
t.insert(i, "let lastSig='',lastSaveAt=0;", indent=1)

i = t.find("const changes=JSON.parse(raw);if(!Array.isArray(changes)||!changes.every(valid))throw Error('Invalid equipment update');")
t.insert(i + 1, """// v38: the tracker re-pushes values that refreshRestore just re-applied, every
// 1.5 s, and each push rewrote all ~700 records (also while a map loads).
// Identical pushes are skipped; real changes are rate limited to one per 3 s.
const sig=changes.map(op=>key(op)+'='+JSON.stringify(op)).sort().join('|');
if(sig===lastSig||((Date.now()-lastSaveAt)<3000)){refreshRestore();return 'equipment-save-duplicate';}
lastSig=sig;""", indent=2)

i = t.find("log('equipment-saved',{changes:changed,fields:records.size});")
assert t.l[i - 1].strip() == 'refreshRestore();', t.l[i - 1]
t.insert(i, 'lastSaveAt=Date.now();', indent=3)

i = t.find("log('equipment-store-ready',{fields:records.size});")
assert t.l[i - 1].strip() == '};', t.l[i - 1]
t.insert(i - 1, "return 'equipment-save-committed';", indent=2)

# 2. saved match options -----------------------------------------------------
SETTINGS = """
// Saved match options: mode/map/mpMode/squad/difficulty/view/radar survive a restart.
(()=>{
 const file='/data/user/0/com.activision.callofduty.wzm310x/files/local-settings.json';
 const version='wzm-1797-settings-v1';
 let saved=null;
 const accept=o=>{if(o&&o.version===version&&o.settings&&typeof o.settings==='object')saved=o.settings;};
 try{accept(JSON.parse(File.readAllText(file)));}catch(_){}
 if(!saved){try{accept(JSON.parse(File.readAllText(file+'.bak')));}catch(_){}}
 const str=(v,d)=>(typeof v==='string'&&v.length>0&&v.length<64)?v:d;
 const num=(v,d,ok)=>ok.includes(v)?v:d;
 const s={
  mode:saved&&saved.mode==='mp'?'mp':'br',
  map:str(saved&&saved.map,''),
  mpMode:str(saved&&saved.mpMode,'war'),
  squad:num(saved&&saved.squad,2,[2,3,4]),
  difficulty:num(saved&&saved.difficulty,0,[0,1,2,3]),
  thirdPerson:saved&&saved.thirdPerson===true,
  radar:saved&&saved.radar===true,
  counts:{}
 };
 if(saved&&saved.counts&&typeof saved.counts==='object'){
  for(const k of Object.keys(saved.counts))if([32,48,64,120].includes(saved.counts[k]))s.counts[k]=saved.counts[k];
 }
 log('settings-loaded',{found:!!saved,mode:s.mode,map:s.map,mpMode:s.mpMode,squad:s.squad});
 const q=v=>JSON.stringify(String(v));
 const toLua=x=>'rawset(_G,"ProjectWZMSavedSettings",{mode='+q(x.mode)+',map='+q(x.map)+',mpMode='+q(x.mpMode)
  +',squad='+x.squad+',difficulty='+x.difficulty+',thirdPerson='+(x.thirdPerson?'true':'false')
  +',radar='+(x.radar?'true':'false')+',counts={'
  +Object.keys(x.counts).map(k=>'['+q(k)+']='+x.counts[k]).join(',')+'}})\\n';
 const cur=s;
 globalThis.labSettingsLua=toLua(cur);
 const libc=Process.getModuleByName('libc.so');
 const rename=new NativeFunction(libc.getExportByName('rename'),'int',['pointer','pointer']);
 const move=(a,b)=>rename(Memory.allocUtf8String(a),Memory.allocUtf8String(b));
 globalThis.labSaveSettings=function(raw){
  try{
   const o=JSON.parse(raw);
   if(!o||typeof o!=='object')throw Error('Invalid settings');
   const n={
    mode:o.mode==='mp'?'mp':'br',
    map:str(o.map,''),
    mpMode:str(o.mpMode,'war'),
    squad:num(o.squad,2,[2,3,4]),
    difficulty:num(o.difficulty,0,[0,1,2,3]),
    thirdPerson:o.thirdPerson===true,
    radar:o.radar===true,
    counts:{}
   };
   if(o.counts&&typeof o.counts==='object'){
    for(const k of Object.keys(o.counts))if([32,48,64,120].includes(o.counts[k]))n.counts[k]=o.counts[k];
   }
   File.writeAllText(file+'.tmp',JSON.stringify({version,updated:new Date().toISOString(),settings:n}));
   move(file,file+'.bak');
   if(move(file+'.tmp',file)!==0)throw Error('Cannot commit settings save');
   Object.assign(cur,n);
   globalThis.labSettingsLua=toLua(cur);
   log('settings-saved',{mode:n.mode,map:n.map,mpMode:n.mpMode});
  }catch(e){log('settings-save-error',{error:String(e)});}
 };
})();
"""
i = t.find("log('equipment-store-ready',{fields:records.size});")
assert t.l[i + 1].strip() == '})();', t.l[i + 1]
t.insert(i + 2, SETTINGS)

# 3. hot-path probe off ------------------------------------------------------
txt = sub1(t.text(), 'this.log=bounded(name,this.path);', 'this.log=false;', 'open-probe')
t = Lines(txt)

# 4. drop dead request-file polling -----------------------------------------
i = t.find('applyBootConfigOnce();')
assert t.l[i - 1].strip() == 'setInterval(()=>{', t.l[i - 1]
end = i + 1
while t.l[end].strip() != '},1000);':
    end += 1
del t.l[i - 1:end + 1]
t.insert(i - 1, 'setInterval(applyBootConfigOnce,1000);', indent=2)

i = t.find('if(!request)for(const d of [dir]){')
j = i
while t.l[j].strip() != '}':
    j += 1
del t.l[i:j + 1]

i = t.find("if(!requested){try{source=File.readAllText(dir+'lobby-bootstrap.lua');}catch(_){}}")
del t.l[i]

# 5. Lua prelude -------------------------------------------------------------
# It is glued in front of the stock bootstrap chunk, so a chunk-level return
# there would silently kill the menu: refuse to build one.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
import lua_check  # noqa: E402
assert lua_check.check('work/cn/lua_prelude.lua', True) == 0, 'prelude failed the strict Lua check'
LUA = io.open('work/cn/lua_prelude.lua', encoding='utf-8').read()

DASHA = ("""  /* Local-only Lua prelude, prepended to every Lua push (cached chunk):
     all-unlock for local loot, Chinese language pack, match score/time limits,
     then an optional lab_extra.lua override, read once. */
  const DSHA_LUA=""" + json.dumps(LUA) + """;""")

DASHA += """
  let labExtraLua=null;
  function labDshaBuiltin(){
   if(labExtraLua===null){
    labExtraLua='';
    try{labExtraLua=File.readAllText(dir+'lab_extra.lua');}
    catch(_){try{labExtraLua=File.readAllText(MEDIA+'lab_extra.lua');}catch(__){}}
    if(labExtraLua)log('lab-extra-loaded',{bytes:labExtraLua.length});
   }
   return DSHA_LUA+(labExtraLua?'\\n'+labExtraLua:'')+'\\n';
  }"""

i = t.find("Interceptor.attach(b.add(0x47ded18),{onEnter(a){this.state=a[0];const ui=b.add(0xb7e0958).readPointer();this.selected=!busy&&!a[0].isNull()&&!ui.isNull()&&Date.now()>next&&a[0].equals(ui);},onLeave(){")
t.insert(i, DASHA)

# 6. keep the stock chunk byte-identical; run the prelude as its own chunk --
# Prepending anything to the stock bootstrap is what broke one boot: the stock
# chunk then returned nil and "waiting-ui-libraries" never advanced. The prelude
# now runs on its own every 4th tick, so a failure there can only cost features.
i = t.find('source=\'rawset(_G,"ProjectWZMMatchMemoryReady",\'+')
assert t.l[i + 2].strip() == "(globalThis.labSavedEquipmentLua||'')+source;", t.l[i + 2]
t.replace(i, """source='rawset(_G,"ProjectWZMMatchMemoryReady",'+
    (globalThis.labCompactPoolState?'true':'false')+');'+
    (globalThis.labSettingsLua||'')+(globalThis.labSavedEquipmentLua||'')+source;
    globalThis.labPreludeSource=labDshaBuiltin();""", indent=4)

i = t.find("else if(result!==lastAuto){lastAuto=result;log('automatic-local-setup',{status,result});}")
t.insert(i + 1, """globalThis.labTick=(globalThis.labTick||0)+1;
    if(globalThis.labTick%4===0&&globalThis.labPreludeSource){
     try{
      getField(L,-10002,loader);
      pushString(L,Memory.allocUtf8String(globalThis.labPreludeSource));
      let ps=call(L,1,1,0);if(ps===0)ps=call(L,0,1,0);
      if(ps!==0){const pe=toString(L,-1,ptr(0));log('prelude-error',{status:ps,err:pe.isNull()?null:pe.readUtf8String().slice(0,200)});}
     }catch(e){log('prelude-ex',{e:String(e).slice(0,200)});}
    }""", indent=4)

# 7. result routing ----------------------------------------------------------
i = t.find("if(status===0&&result.startsWith('equipment-save:')){globalThis.labSaveEquipment(result.slice(15));result='equipment-save-committed';}")
t.replace(i, """if(status===0&&result.startsWith('equipment-save:'))result=globalThis.labSaveEquipment(result.slice(15));
    if(status===0&&result.startsWith('settings-save:')){globalThis.labSaveSettings(result.slice(14));result='settings-save-committed';}""", indent=4)

# 8. status tag --------------------------------------------------------------
i = t.find("const out={tag:'v18',uptimeMs:Date.now()-labBootT0,diag:!!globalThis.labDiagOn,")
t.replace(i, "const out={tag:'v22',uptimeMs:Date.now()-labBootT0,diag:!!globalThis.labDiagOn,", indent=4)
i = t.find('try{out.stream=globalThis.labStreamState||null;}catch(_){}')
t.insert(i + 1, 'try{out.settings=!!globalThis.labSettingsLua;}catch(_){}', indent=4)

# 9. bot tuning surfaces ------------------------------------------------------
# The offline Lua menu passes the picked difficulty to the engine lobby call.
# An override lets a probe or lab_extra.lua push the raw engine value past the
# four UI tiers (0..7) without touching the menu; unset it and nothing changes.
txt = sub1(t.text(),
           'state.difficulty=selection.botDifficulty or 0',
           "local _bs=tonumber(rawget(_G,'ProjectWZMBotSkill')) "
           "state.difficulty=_bs and math.max(0,math.min(7,_bs)) or selection.botDifficulty or 0",
           'bot-skill-override')
t = Lines(txt)

# Bot behaviour lives in data, not in a dvar: record which bot assets the pack
# loader resolves so a probe can name the file to override next time. This only
# costs one Set lookup per unresolved path and never writes unless diag is on.
i = t.find('const loggedLootAliases310=new Set();')
t.insert(i + 1, 'const botAssetNames310=new Set();')
i = t.find('let name;try{name=a[0].readUtf8String();}catch(_){return;}')
t.insert(i + 1,
         "if(name&&botAssetNames310.size<24&&!botAssetNames310.has(name)&&(name.indexOf('bot')>=0||name.indexOf('Bot')>=0)){"
         "botAssetNames310.add(name);log('bot-asset',{name});}", indent=1)

out = t.text()
open(DST, 'w', encoding='utf-8', newline='\n').write(out)
print('wrote %s: %d bytes, %d lines' % (DST, len(out.encode()), out.count('\n') + 1))

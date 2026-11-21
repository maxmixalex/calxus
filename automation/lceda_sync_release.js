/* Deliver a fixed Calxus Git commit to the user's real local project folder.
 * No EDA canvas calls, shell commands, git mutation, or private firmware writes.
 * args: {stage:'plan'|'sync', manifest?:{repo,commit,files:[{path,size,sha256}]},
 *        manifestPath?, commit?, root?, offset?:0, limit?:8, budgetMs?:42000}
 * Default stage is read-only 'plan'. Never sync a branch name such as main.
 * Reported SHA-256 values must be compared with the manifest in the container;
 * the portable fallback is used because this client's crypto.subtle is absent.
 */
const args=__CLI__.args||{};
const ROOT=(args.root||'D:/Works/Calc/Calxus/').replace(/\/?$/,'/');
const stage=args.stage||'plan';
if(!['plan','sync'].includes(stage))throw new Error('Unsupported release stage');
let manifest=args.manifest;
if(!manifest){const f=await eda.sys_FileSystem.readFileFromFileSystem(args.manifestPath||ROOT+'engineering/release-manifest.json');if(!f)throw new Error('Missing fixed-commit release manifest');manifest=JSON.parse(await f.text());}
const repo=manifest.repo||'maxmixalex/calxus',commit=manifest.commit;
if(repo!=='maxmixalex/calxus'||!/^[0-9a-f]{40}$/i.test(commit||''))throw new Error('Only the authorized repository and a full immutable commit SHA are accepted');
if(args.commit&&args.commit!==commit)throw new Error('Requested commit differs from manifest');
if(!Array.isArray(manifest.files)||!manifest.files.length)throw new Error('Empty release manifest');
const seen=new Set();
function safePath(path){
  if(typeof path!=='string'||!path||/[\\:\x00-\x1f]/.test(path)||path.startsWith('/')||path.endsWith('/'))return false;
  const parts=path.split('/');
  if(parts.some(p=>!p||p==='.'||p==='..'||p.toLowerCase()==='.git'))return false;
  const lower=path.toLowerCase();
  return !lower.startsWith('firmware/local-build/')&&lower!=='firmware/local-build'&&lower!=='exports/calxus_private_firmware.zip';
}
for(const f of manifest.files){
  if(!safePath(f.path)||seen.has(f.path.toLowerCase()))throw new Error('Unsafe or duplicate release path '+f.path);
  seen.add(f.path.toLowerCase());
  if(!Number.isSafeInteger(f.size)||f.size<0||!/^[0-9a-f]{64}$/i.test(f.sha256||''))throw new Error('Invalid size/SHA256 for '+f.path);
  if(f.mode&&!['100644','100755'].includes(String(f.mode)))throw new Error('Only ordinary Git blobs may be synchronized: '+f.path);
}
const offset=args.offset||0,limit=args.limit||8;
if(!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1)throw new Error('Invalid batch bounds');
const selected=manifest.files.slice(offset,offset+limit);
if(stage==='plan')return {ok:true,stage,repo,commit,total:manifest.files.length,offset,selected:selected.map(f=>({path:f.path,size:f.size,sha256:f.sha256})),writes:0};

// Self-contained SHA-256. All arithmetic is unsigned 32-bit. No external code
// is loaded; constants are the SHA-256 fractional cube roots of the first primes.
function portableSha256(input){
  const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
  const H=new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
  const n=Math.ceil((input.length+9)/64)*64,data=new Uint8Array(n),view=new DataView(data.buffer),W=new Uint32Array(64);
  data.set(input);data[input.length]=0x80;view.setUint32(n-8,Math.floor(input.length/0x20000000),false);view.setUint32(n-4,(input.length*8)>>>0,false);
  const rr=(x,n)=>(x>>>n)|(x<<(32-n));
  for(let off=0;off<n;off+=64){
    for(let i=0;i<16;i++)W[i]=view.getUint32(off+i*4,false);
    for(let i=16;i<64;i++){const x=W[i-15],y=W[i-2],s0=rr(x,7)^rr(x,18)^(x>>>3),s1=rr(y,17)^rr(y,19)^(y>>>10);W[i]=(W[i-16]+s0+W[i-7]+s1)>>>0;}
    let [a,b,c,d,e,f,g,h]=H;
    for(let i=0;i<64;i++){const s1=rr(e,6)^rr(e,11)^rr(e,25),ch=(e&f)^(~e&g),t1=(h+s1+ch+K[i]+W[i])>>>0,s0=rr(a,2)^rr(a,13)^rr(a,22),maj=(a&b)^(a&c)^(b&c),t2=(s0+maj)>>>0;h=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
    const state=[a,b,c,d,e,f,g,h];for(let i=0;i<8;i++)H[i]=(H[i]+state[i])>>>0;
  }
  return Array.from(H).map(n=>n.toString(16).padStart(8,'0')).join('');
}
const nativeCrypto=typeof crypto!=='undefined'&&!!crypto.subtle&&typeof crypto.subtle.digest==='function';
if(!nativeCrypto&&(portableSha256(new Uint8Array())!=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'||portableSha256(new TextEncoder().encode('abc'))!=='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'))throw new Error('Portable SHA-256 self-check failed');
async function digest(bytes){return nativeCrypto?Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(n=>n.toString(16).padStart(2,'0')).join(''):portableSha256(bytes);}
async function readBytes(path){
  // Some client versions wrap a missing-file error in a File; never treat it as user data.
  if(await eda.sys_FileSystem.existsPathInFileSystem(path)!==true)return null;
  const f=await eda.sys_FileSystem.readFileFromFileSystem(path);
  return f?new Uint8Array(await f.arrayBuffer()):null;
}
const directories=new Set();
async function directory(path){if(directories.has(path))return;const exists=await eda.sys_FileSystem.existsPathInFileSystem(path);if(!exists&&await eda.sys_FileSystem.createDirectoryInFileSystem(path)!==true)throw new Error('Cannot create delivery directory '+path);directories.add(path);}
function mergeIgnore(original,release){
  if(original[0]===0xff&&original[1]===0xfe)throw new Error('Unexpected UTF16 .gitignore');
  const existing=new TextDecoder('utf-8',{fatal:true}).decode(original),incoming=new TextDecoder('utf-8',{fatal:true}).decode(release);
  const lines=new Set(existing.split(/\r?\n/)),add=[];
  for(const line of incoming.split(/\r?\n/)){if(line.trim()&&!line.startsWith('#')&&!lines.has(line)){add.push(line);lines.add(line);}}
  for(const line of ['/firmware/local-build/','/exports/Calxus_private_firmware.zip'])if(!lines.has(line)){add.push(line);lines.add(line);}
  if(!add.length)return original;
  const extra=new TextEncoder().encode((original.length&&original[original.length-1]!==10?'\n':'')+add.join('\n')+'\n');
  const merged=new Uint8Array(original.length+extra.length);merged.set(original);merged.set(extra,original.length);return merged;
}
const started=Date.now(),report={ok:false,stage,repo,commit,total:manifest.files.length,offset,processed:0,nextOffset:offset,sha256Engine:nativeCrypto?'crypto.subtle':'portable-js',independentSandboxDigestComparisonRequired:!nativeCrypto,files:[],failures:[],createdAt:new Date().toISOString()};
for(const entry of selected){
  if(report.processed&&Date.now()-started>(args.budgetMs||42000))break;
  const target=ROOT+entry.path;
  const item={path:entry.path,size:entry.size,expectedSha256:entry.sha256.toLowerCase(),target};
  try{
    const old=await readBytes(target);
    if(entry.path!=='.gitignore'&&old&&old.length===entry.size&&await digest(old)===item.expectedSha256){item.action='already-matches';item.readbackBytes=old.length;item.readbackSha256=item.expectedSha256;item.pass=true;}
    else{
      const url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+entry.path.split('/').map(encodeURIComponent).join('/');
      const response=await eda.sys_ClientUrl.request(url,'GET');
      if(!response||response.status!==200||!response.ok)throw new Error('Native URL request failed, HTTP '+response?.status);
      const downloaded=new Uint8Array(await (await response.blob()).arrayBuffer());
      item.downloadBytes=downloaded.length;item.downloadSha256=await digest(downloaded);
      if(downloaded.length!==entry.size||item.downloadSha256!==item.expectedSha256)throw new Error('Downloaded bytes/SHA256 differ from fixed manifest');
      let desired=downloaded;
      if(entry.path==='.gitignore'){
        desired=mergeIgnore(old||new Uint8Array(),downloaded);item.action='merge-ignore';item.originalBytes=old?.length||0;item.sourceManifestVerified=true;
      }else item.action='write';
      const expectedTargetSha256=await digest(desired);
      await directory(target.slice(0,target.lastIndexOf('/')));
      const saved=await eda.sys_FileSystem.saveFileToFileSystem(target,new Blob([desired]),undefined,true);
      item.saved=saved===true;if(saved!==true)throw new Error('Native filesystem write returned false');
      const actual=await readBytes(target);if(!actual)throw new Error('Saved file cannot be read back');
      item.readbackBytes=actual.length;item.readbackSha256=await digest(actual);item.expectedTargetSha256=expectedTargetSha256;
      if(actual.length!==desired.length||item.readbackSha256!==expectedTargetSha256)throw new Error('Saved bytes/SHA256 readback mismatch');
      if(entry.path==='.gitignore'){
        let preserved=true;for(let i=0;i<(old?.length||0);i++)if(old[i]!==actual[i]){preserved=false;break;}
        item.originalBytesPreserved=preserved;if(!preserved)throw new Error('Existing .gitignore prefix was modified');
      }
      item.pass=true;
    }
    report.files.push(item);report.processed++;report.nextOffset++;
  }catch(error){item.pass=false;item.error=String(error?.message||error);report.files.push(item);report.failures.push({path:entry.path,error:item.error});break;}
}
report.ok=report.failures.length===0;
report.complete=report.ok&&report.nextOffset===manifest.files.length;
report.elapsedMs=Date.now()-started;
const reportPath=ROOT+'engineering/release-sync-'+commit.slice(0,12)+'-'+offset+'.json';
await directory(ROOT+'engineering');
const saved=await eda.sys_FileSystem.saveFileToFileSystem(reportPath,new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),undefined,true);
if(saved!==true){report.ok=false;report.failures.push({path:reportPath,error:'Sync report could not be saved'});}
return {...report,reportPath,reportSaved:saved===true};

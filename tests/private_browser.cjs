/* Private owner onboarding and two-device integration, with temporary data. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');

(async()=>{
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'tennis-private-'));
  const setupToken=crypto.randomBytes(32).toString('hex');
  const server=spawn(process.env.PYTHON_BIN||'python3',['server.py','--port','0'],{
    cwd:path.resolve(__dirname,'..'),env:{...process.env,TENNIS_DB:path.join(directory,'private.sqlite3'),TENNIS_PRIVATE:'1',TENNIS_SETUP_TOKEN:setupToken,TENNIS_SECURE_COOKIE:'0'},stdio:['ignore','pipe','pipe']
  });
  let browser;
  try{
    const port=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('No arrancó el servidor privado')),10000);
      server.on('error',reject);server.stderr.on('data',data=>process.stderr.write(data));
      server.stdout.on('data',data=>{const match=String(data).match(/puerto (\d+)/);if(match){clearTimeout(timer);resolve(match[1])}});
    });
    browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox']});
    const pcContext=await browser.newContext({viewport:{width:1440,height:1000}});
    const mobileContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
    const pc=await pcContext.newPage(),mobile=await mobileContext.newPage();
    const errors=[];for(const page of [pc,mobile]){page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000)}
    const address=`http://127.0.0.1:${port}`;
    await pc.goto(address);await pc.getByRole('heading',{name:'Crea tu cuenta privada'}).waitFor();
    await pc.locator('[name=token]').fill(setupToken);await pc.locator('[name=name]').fill('Mi escuela');await pc.locator('[name=email]').fill('owner@example.test');
    await pc.locator('[name=password]').fill('PrivateOwnerPassword2026!');await pc.locator('[name=confirmation]').fill('PrivateOwnerPassword2026!');
    await pc.getByRole('button',{name:'Crear mi cuenta y entrar'}).click();
    await pc.getByRole('heading',{name:'Un grupo para cada jugador'}).waitFor();
    assert.equal(await pc.locator('[data-action=demo]').count(),0);
    console.log('PASS: primer inicio privado, sin cuentas demo');
    await mobile.goto(address);
    assert.equal(await mobile.locator('[data-action=demo]').count(),0);
    await mobile.locator('[name=email]').fill('owner@example.test');await mobile.locator('[name=password]').fill('PrivateOwnerPassword2026!');await mobile.getByRole('button',{name:'Entrar a mi espacio'}).click();
    await mobile.getByRole('heading',{name:'Un grupo para cada jugador'}).waitFor();
    for(const page of [pc,mobile])await page.locator('[data-page=catalog]').click();
    await pc.locator('[data-action=catalog-form][data-kind=level]').click();await pc.locator('dialog [name=name]').fill('Nivel privado compartido');await pc.locator('dialog').getByRole('button',{name:'Guardar',exact:true}).click();
    await mobile.getByText('Nivel privado compartido',{exact:true}).waitFor();
    assert.equal(await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    console.log('PASS: la cuenta privada comparte datos en PC y móvil');
    await pc.getByRole('button',{name:'Cambiar mi contraseña'}).click();
    await pc.locator('dialog [name=current_password]').fill('PrivateOwnerPassword2026!');await pc.locator('dialog [name=password]').fill('NewPrivatePassword2026!');await pc.locator('dialog').getByRole('button',{name:'Cambiar contraseña',exact:true}).click();
    await mobile.getByRole('heading',{name:'Bienvenido a la escuela'}).waitFor();
    await mobile.locator('[name=email]').fill('owner@example.test');await mobile.locator('[name=password]').fill('NewPrivatePassword2026!');await mobile.getByRole('button',{name:'Entrar a mi espacio'}).click();
    await mobile.getByRole('heading',{name:'Un grupo para cada jugador'}).waitFor();
    console.log('PASS: cambio de contraseña revoca la sesión del otro dispositivo');
    assert.deepEqual(errors,[]);
  }finally{
    if(browser)await browser.close();server.kill('SIGTERM');
    await new Promise(resolve=>{if(server.exitCode!==null||server.signalCode!==null)resolve();else server.once('exit',resolve)});
    fs.rmSync(directory,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1});

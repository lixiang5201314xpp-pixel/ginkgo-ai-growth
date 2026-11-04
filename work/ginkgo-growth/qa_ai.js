async (page)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.getByText('已完成可执行部分；请查看所需接入或核实事项',{exact:true}).waitFor({timeout:15000});
 const result=await page.locator('#modalBody').innerText();
 if(!result.includes('搜索 4 次')||!result.includes('准备 1 条回复'))throw Error('All-job results missing');
 await page.getByRole('button',{name:'关闭',exact:true}).click();
 await page.locator('nav button[data-page="aiSettings"]').click();
 await page.getByRole('heading',{name:'让 AI，开始为球馆工作。',exact:true}).waitFor();
 if(await page.locator('input[name="api_key"]').inputValue())throw Error('Key returned to form');
 await page.getByRole('button',{name:'测试密钥和模型连接',exact:true}).click();
 await page.locator('#testAIResult').filter({hasText:'验证通过'}).waitFor();
 await page.getByRole('button',{name:'加密保存配置',exact:true}).click();
 await page.locator('#aiSaveResult').filter({hasText:'已加密保存'}).waitFor();
 await page.locator('nav button[data-page="content"]').click();
 await page.getByRole('heading',{name:'四个平台 · AI 小程序引流内容',exact:true}).waitFor();
 if(await page.locator('[data-ai-copy]').count()!==4)throw Error('Four native platform drafts missing');
 await page.locator('nav button[data-page="discover"]').click();
 await page.getByRole('heading',{name:'AI 搜索到的待核实网页',exact:true}).waitFor();
 if(await page.locator('[data-candidate]').count()!==4)throw Error('Candidate count wrong');
 await page.locator('nav button[data-page="automate"]').click();
 await page.getByRole('heading',{name:'把三步，交给执行任务。',exact:true}).waitFor();
 await page.screenshot({path:'output/playwright/ginkgo-ai-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile overflow');
 await page.screenshot({path:'output/playwright/ginkgo-ai-mobile.png',fullPage:true});
 const guides=[];
 for(const [platform,name] of [['douyin','抖音'],['kuaishou','快手'],['xiaohongshu','小红书'],['channels','微信']]){
  await page.goto('http://127.0.0.1:8818/api/match-center/growth/club/'+platform+'-training');
  await page.locator('#miniappGuide').filter({hasText:name+'内打开银杏奖牌'}).waitFor();guides.push(platform);
 }
 await page.locator('#chatForm textarea').fill('孩子每周来两次，该怎么选择课程？');
 await page.locator('#chatForm input[type=checkbox]').check();
 await page.getByRole('button',{name:'向 AI 提问',exact:true}).click();
 await page.locator('#chatResult').filter({hasText:'我们是银杏乒乓球俱乐部'}).waitFor();
 await page.locator('#chatForm textarea').fill('那一次上多久呢？');
 await page.getByRole('button',{name:'继续提问',exact:true}).click();
 await page.locator('#chatResult').filter({hasText:'我们是银杏乒乓球俱乐部'}).waitFor();
 await page.screenshot({path:'output/playwright/ginkgo-ai-public-chat.png',fullPage:true});
 console.log(JSON.stringify({passed:true,errors,platformGuides:guides,realPlatformActions:0,paidRequests:0}));
 if(errors.length)throw Error(errors.join(';'));
}

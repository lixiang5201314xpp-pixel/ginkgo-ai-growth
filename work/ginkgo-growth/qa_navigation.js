async (page) => {
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const tests=[];
  const pages=[['discover','寻找，正在想打球的人。'],['leads','每一条需求，都好好回应。'],['content','让想打球的人，也能找到你。'],['campaigns','把下一步，说清楚。'],['inquiries','有人来问，及时接住。'],['connections','渠道状态，如实可见。'],['overview','让需求，遇见合适的球局。']];
  for(const [name,heading] of pages){
    await page.locator(`nav button[data-page="${name}"]`).click();
    await page.getByRole('heading',{name:heading,exact:true}).waitFor();
    tests.push({name,visible:true});
  }
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
  console.log(JSON.stringify({tests,errors,mobileOverflow:overflow}));
}

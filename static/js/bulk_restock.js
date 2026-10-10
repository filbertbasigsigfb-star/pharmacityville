(() => {
  'use strict';
  function boxes(){return Array.from(document.querySelectorAll('[data-restock-select]'));}
  function update(){
    const checks=boxes();const selected=checks.filter(x=>x.checked).length;
    const count=document.getElementById('restock-count');if(count) count.textContent=`${selected} selected`;
    const button=document.getElementById('restock-review');if(button)button.disabled=selected===0;
    const all=document.getElementById('restock-select-all');
    if(all){all.checked=checks.length>0&&selected===checks.length; all.indeterminate=selected>0&&selected<checks.length;}
  }
  // Delegate events because the admin live refresh swaps the medicine table.
  document.addEventListener('change',(event)=>{
    if(event.target?.id==='restock-select-all'){
      boxes().forEach(x=>{x.checked=event.target.checked;});update();
    } else if(event.target?.matches('[data-restock-select]')) update();
  });
  document.addEventListener('DOMContentLoaded',update);
})();

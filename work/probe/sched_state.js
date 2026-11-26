(function(){
 // Read-only thread table for the scheduling check: name, nice, allowed CPUs.
 // Sent with: python work/lab.py send work/probe/sched_state.js
 var rows=[];
 var tasks=Process.enumerateThreads();
 for(var i=0;i<tasks.length;i++){
  var t=tasks[i],p='/proc/self/task/'+t.id,nice='?',cpus='?';
  try{
   var s=File.readAllText(p+'/stat');
   var f=s.slice(s.lastIndexOf(')')+2).split(' ');
   nice=String(f[16]);
  }catch(e){}
  try{
   var st=File.readAllText(p+'/status');
   var m=st.match(/Cpus_allowed_list:\s*(\S+)/);
   if(m)cpus=m[1];
  }catch(e){}
  rows.push((t.name||'?')+' nice='+nice+' cpu='+cpus);
 }
 return rows.join('\n');
})()

function get_words(s) {
  s = s.toLowerCase().trim().split(/\s+/).filter(w => w.length>0);
  s = [...new Set(s)];
  return s;
}
function mkTag(s) {
  const div = document.createElement("div");
  div.innerHTML = s;
  return div.children[0];
}

function getVal(id) {
  const elm = document.getElementById(id);
  if (elm == null) {
    console.log("No se ha encontrado #"+ id);
    return null;
  }
  const val = elm.value;
  if (val == null || val.length==0) return null;
  const tp = elm.getAttribute("data-type") || elm.getAttribute("type");
  if (tp == "number") {
    const num = Number(val);
    if (isNaN(num)) return null;
    return num;
  }
  return val;
}

function isCross(arr1, arr2){
  if (arr1.length==0 || arr2.length==0) return false;
  let i;
  for (i=0; i<arr1.length;i++) {
    if (arr2.includes(arr1[i])) return true;
  }
  return false;
}
function qs(slc, fnc) {
  const arr = document.querySelectorAll(slc);
  if (arr.length == 0 || fnc == null) return arr;
  return Array.from(arr).map(fnc).filter((i)=>i!=null);
}
function filter(slc, fnc) {
  const ok = [];
  const ko = [];
  document.querySelectorAll(slc).forEach((i) => {
    (fnc(i)?ok:ko).push(i);
  });
  return {
    ok, ko
  }
}
function fe(slc, fnc) {
	document.querySelectorAll(slc).forEach(fnc);
}
function get_ranges() {
    const rgs = {};
    Array.from(arguments).forEach(k => {
      let mn = getVal(k+"_min");
      let mx = getVal(k+"_max");
      if (mn == null || mx == null) return;
      rgs[k]={"min":mn, "max":mx};
    })
    return rgs;
}


function filtrar() {
  const show = getVal("list");
  const hdsh = getVal("chkhideshow");
  const chhs = qs(".chkhideshow input", (i) => i.checked?i.id:null);
  const rgs = get_ranges("price", "rate", "reviews");
  const antiguedad = (()=>{
    let aux = getVal("antiguedad");
    if (aux!=null && aux>=0) return aux;
    return null;
  })();
  const { ok, ko } = filter("div.game", (i) => {
    const j = GAME[i.id];
    if (j==null) {
      console.log(i.id, "no encontrado", i);
      return true;
    }
    if (show=="G" && !j.gamepass) return false;
    if (show=="F" && !j.tags.includes("Free")) return false;
    if (show=="T" && !j.trial) return false;
    if (antiguedad!=null && j.antiquity!=null && j.antiquity>antiguedad) return false;
    
    const fl = (() => {
      if (chhs.length == 0) {
        if (hdsh[0]=='S') return false;
        if (hdsh[0]=='H') return true;
      }
      const hs = chhs.filter(v => j.tags.includes(v));
      if (hdsh == "SO") return hs.length  > 0;
      if (hdsh == "HO") return hs.length == 0;
      if (hdsh == "SA") return hs.length == chhs.length;
      if (hdsh == "HA") return hs.length != chhs.length;
      console.log(hdsh, chhs, j.tags, hs);
    })();
    if (!fl) return false;

    const ok_rgs = Object.entries(rgs).map(kv => {
      const [k, value] = kv;
      const vl = j[k];
      if (vl==null) {
        console.log(i.id, "no tine", k);
        return true;
      }
      return (vl >= value['min']) && (vl <= value['max']);
    });
    if (ok_rgs.includes(false)) return false;

    return true;
  });
  ok.forEach((i) => i.style.display = "");
  ko.forEach((i) => i.style.display = "none");
  if (ko.length==0) {
    document.title = `${ok.length} juegos`;
  } else {
    document.title = `${ok.length}/${ok.length+ko.length} juegos`;
  }
  document.getElementById("games").classList.remove("hideIfJS")
}
document.addEventListener('DOMContentLoaded', () => {
  const opts = document.getElementById("antiguedad").options;
  //const opts = document.createElement("select").options
  const head = opts.length - 1;
  const done = [];
  const days_to_lab = (ant) => {
    if (ant<30) return {'txt': 'día', num: ant};
    if (ant<365) return {'txt': 'mes', num: Math.ceil(ant/30), 's': 'es'};
    return {'txt': 'año', num: Math.ceil(ant/365)};
  }
  Array.from(opts).reverse().forEach((o, i)=>{
    const ant = Number(o.value)+ANTIQUITY;
    const lab = days_to_lab(ant)
    if (done.includes(lab.txt+lab.num)) {
      o.remove();
      return;
    }
    if (i>0 && i<head && (lab.num%2)==1) {
      o.remove();
      return;
    }
    done.push(lab.txt+lab.num);
    if (lab.txt!='día' || ANTIQUITY>0) {
      o.textContent = lab.num + " " + lab.txt +(lab.num!=1?(lab.s??'s'):"");
    }
  })
  fe("input, select", (i) => {
    i.addEventListener('change', filtrar);
  })
  filtrar();
}, false);

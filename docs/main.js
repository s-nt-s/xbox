function get_words(s) {
  s = s.toLowerCase().trim().split(/\s+/).filter(w => w.length>0);
  s = [...new Set(s)];
  return s;
}

function getVal(id) {
  const elm = document.getElementById(id);
  if (elm == null) {
    console.log("No se ha encontrado #"+ id);
    return null;
  }
  const val = elm.value;
  if (val == null || val.length==0) return null;
  return val;
}
function getNum(id) {
  const val = getVal(id);
  if (val == null || val.length==0) return null;
  const num = parseInt(val);
  if (isNaN(num)) return null;
  return num;
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
      let mn = getNum(k+"_min");
      let mx = getNum(k+"_max");
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
  /*
  const antiguedad = (()=>{
    let aux = getNum("antiguedad");
    if (aux!=null && aux>=0) return aux;
    return null;
  })();
  */
  const { ok, ko } = filter("div.game", (i) => {
    const j = GAME[i.id];
    if (j==null) {
      console.log(i.id, "no encontrado", i);
      return true;
    }
    if (show=="G" && !j.gamepass) return false;
    if (show=="F" && !j.tags.includes("Free")) return false;
    if (show=="T" && !j.trial) return false;
    //if (antiguedad!=null && j.antiguedad!=null && j.antiguedad>antiguedad) return false;
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
  /*
  const hoy = new Date().getTime();
  Object.values(GAME).forEach(g => {
    if (g.releaseDate==null) return;
    const r = g.releaseDate.split("-")
    const d = new Date(r[0], r[1], r[2]).getTime();
    g.antiguedad = (hoy-d) / (1000 * 3600 * 24)
  });
  */
  fe("input, select", (i) => {
    i.addEventListener('change', filtrar);
  })
  filtrar();
}, false);

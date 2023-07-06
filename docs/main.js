function get_words(s) {
  s = s.toLowerCase().trim().split(/\s+/).filter(w => w.length>0);
  s = [...new Set(s)];
  return s;
}
function mkTag(s) {
  const div = document.createElement("div");
  div.innerHTML = s;
  div.querySelectorAll("*[id]").forEach(d=>{
    const bak = document.getElementById("bak_"+d.id);
    if (bak == null) return;
    if (bak.value.length) {
      if (d.hasAttribute("value") != null) d.setAttribute("value", bak.value);
      if (d.tagName == "SELECT") Array.from(d.options).forEach(o=> {
        if (o.getAttribute("value") == bak.value) o.setAttribute("selected", "selected");
        else o.removeAttribute("selected");
      });
    }
    d.addEventListener('change', (ev) => {
      bak.value = ev.target.value;
    })
  })
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
  const antiguedad = (()=>{
    let aux = getNum("antiguedad");
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
    if (antiguedad!=null && j.antiguedad!=null && j.antiguedad>antiguedad) {
      console.log(j);
      return false;
    }
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
  const ants = []
  const hoy = new Date().getTime();
  Object.values(GAME).forEach(g => {
    if (g.releaseDate==null) return;
    const r = g.releaseDate.split("-").map(x=>Number(x))
    const d = new Date(r[0], r[1]-1, r[2]).getTime();
    g.antiguedad = (hoy-d) / (1000 * 3600 * 24);
    const ant = Math.ceil(g.antiguedad);
    if (!ants.includes(ant)) ants.push(ant);
  });
  const opts = [];
  ants.sort((a, b)=>a-b).forEach((d, i)=>{
    let opt=null;
    if (i<4) {
      opt = `<option value="${d}">${d} día${d==1?"":"s"}</option>`;
    } else if (d<365) {
      const ms = Math.ceil(d/30);
      opt = `<option value="${ms*30}">${ms} mes${ms==1?"":"es"}</option>`;
    } else {
      const ys = Math.ceil(d/365);
      opt = `<option value="${ys*365}">${ys} año${ys==1?"":"s"}</option>`;
    }
    if (opt!=null && !opts.includes(opt)) opts.push(opt);
  })
  if (opts.length) {
    opts[opts.length-1] = opts[opts.length-1].replace("<option ", "<option selected ");
    document.getElementById("rangos").appendChild(mkTag(`
      <p>
        <label for="antiguedad">Antiguedad:
        <select id="antiguedad">
          ${opts.join("\n")}
        </select> o menos
        </label>
      </p>
    `));
  }
  fe("input, select", (i) => {
    i.addEventListener('change', filtrar);
  })
  filtrar();
}, false);

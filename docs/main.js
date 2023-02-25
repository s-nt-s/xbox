function get_words(s) {
  s = s.toLowerCase().trim().split(/\s+/).filter(w => w.length>0);
  s = [...new Set(s)];
  return s;
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
function filtrar() {
  const show = document.querySelector("#list").value;
  const nShow = Number(show);
  const hdsh = document.querySelector("#chkhideshow").value;
  const chhs = qs(".chkhideshow input", (i) => i.checked?i.id:null);
  const { ok, ko } = filter("div.game", (i) => {
    const j = GAME[i.id];
    if (j==null) {
      console.log(i.id, "no encontrado", i);
      return true;
    }
    if (show=="G" && !j.gamepass) return false;
    if (show=="F" && !j.tags.includes("Free")) return false;
    if (!isNaN(nShow) && (j.price == 0 || j.price > nShow)) return false;
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
    return true;
  });
  ok.forEach((i) => i.style.display = "");
  ko.forEach((i) => i.style.display = "none");
  if (ko.length==0) {
    document.title = `${ok.length} juegos`;
  } else {
    document.title = `${ok.length}/${ok.length+ko.length} juegos`;
  }
}
document.addEventListener('DOMContentLoaded', () => {
  fe("input, select", (i) => {
    i.addEventListener('change', filtrar);
  })
  filtrar();
}, false);

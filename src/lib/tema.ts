// Roda antes da primeira pintura para aplicar o tema salvo (ou o do sistema) sem piscar.
export const SCRIPT_TEMA = `(function(){try{var t=localStorage.getItem("meridian_theme");if(t!=="light"&&t!=="dark"){t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

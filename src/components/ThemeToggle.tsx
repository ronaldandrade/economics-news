"use client";

export function ThemeToggle() {
  function alternar() {
    const atual = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const proximo = atual === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", proximo);
    try {
      localStorage.setItem("meridian_theme", proximo);
    } catch {}
  }

  // Os dois rótulos ficam no HTML e o CSS mostra o certo conforme data-theme,
  // assim o servidor não precisa saber o tema escolhido.
  return (
    <button className="theme-btn" type="button" aria-label="Alternar entre tema claro e escuro" onClick={alternar}>
      <svg className="icon-sun" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="4"></circle>
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"></path>
      </svg>
      <svg className="icon-moon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
      </svg>
      <span className="theme-label theme-label--to-dark">Modo Escuro</span>
      <span className="theme-label theme-label--to-light">Modo Claro</span>
    </button>
  );
}

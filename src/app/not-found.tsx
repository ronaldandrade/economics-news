import Link from "next/link";
import { Masthead } from "@/components/Editorial";

export default function NaoEncontrada() {
  return (
    <>
      <Masthead />
      <main className="main-content container">
        <section className="empty-state">
          <h2>Página não encontrada</h2>
          <p>A matéria pode ter mudado de endereço ou ainda não foi publicada.</p>
          <Link href="/" className="btn-primary">
            Voltar à capa
          </Link>
        </section>
      </main>
    </>
  );
}

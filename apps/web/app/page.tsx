import Chat from "./chat";

export default function Home() {
  return (
    <main className="min-vh-100 d-flex flex-column align-items-center justify-content-center bg-body-tertiary p-3">
      <h1 className="h3 mb-2 text-center">Asystent Laika 🧠</h1>
      <p className="text-muted mb-4 text-center" style={{ maxWidth: "600px" }}>
        Twój osobisty tłumacz z naukowego na nasze. Pytaj o badania z bazy SWPS, a opowiem Ci o nich po ludzku!
      </p>
      <Chat />
    </main>
  );
}
import Link from "next/link";

export const metadata = {
  title: "ProrabTask — ИИ-смета, объекты и задачи для прораба",
  description:
    "Telegram-бот и приложение ProrabTask: ИИ считает смету по голосу или тексту, ведите объекты, задачи и бригаду в одном месте.",
};

const FEATURES = [
  {
    title: "Смета за минуту",
    text: "Опишите объект голосом или текстом — ИИ посчитает материалы, объём работ и соберёт смету с ценами.",
  },
  {
    title: "Объекты и задачи",
    text: "Заводите стройплощадки, ставьте задачи бригаде и следите за статусом каждого этапа.",
  },
  {
    title: "Прораб и рабочие — в одной системе",
    text: "У прораба и рабочего разные экраны: прораб раздаёт задачи, рабочий отмечает выполнение и пишет в чат объекта.",
  },
  {
    title: "PDF и экспорт",
    text: "Готовую смету можно отправить заказчику в PDF прямо из Telegram.",
  },
  {
    title: "Вход без паролей",
    text: "Войти можно по Telegram-аккаунту или через passkey — без лишних форм.",
  },
  {
    title: "Приложение на телефоне",
    text: "ProrabTask работает как PWA — добавьте значок на экран и используйте как обычное приложение.",
  },
];

const STEPS = [
  { title: "Войдите", text: "Через Telegram или passkey — это занимает меньше минуты." },
  { title: "Создайте объект", text: "Добавьте стройплощадку и пригласите рабочих по ссылке." },
  { title: "Ставьте задачи", text: "Раздайте работы бригаде и следите за выполнением в одном списке." },
  { title: "Считайте смету", text: "Опишите объект голосом или текстом — получите готовую смету." },
];

const FAQ = [
  {
    q: "Это бесплатно?",
    a: "Вы можете зайти и попробовать сервис. Условия тарифов и подписки уточняйте внутри бота — они могут меняться.",
  },
  {
    q: "Как ИИ считает смету?",
    a: "Вы описываете объект голосовым или текстовым сообщением — объём работ, материалы, пожелания. Бот анализирует описание и сопоставляет его с базой расценок и материалов, формируя предварительную смету. Итоговые цифры стоит проверить перед отправкой заказчику.",
  },
  {
    q: "Можно ли пригласить рабочих в бригаду?",
    a: "Да, в разделе объекта есть ссылка-приглашение — рабочий переходит по ней, попадает в объект и видит свои задачи.",
  },
  {
    q: "На каких устройствах работает?",
    a: "Бот работает в Telegram на любом устройстве. Веб-приложение открывается в браузере телефона или компьютера и добавляется на главный экран как обычное приложение.",
  },
  {
    q: "Что будет с моими данными, если я удалю аккаунт?",
    a: "Данные объектов, задач и профиля можно удалить по запросу. Подробнее — в разделе «Обработка данных и конфиденциальность» ниже.",
  },
];

export default function HomePage() {
  return (
    <main className="container">
      <section className="card hero">
        <p className="eyebrow">PRORABTASK</p>
        <h1>ИИ-смета, объекты и задачи для прораба — в Telegram и на телефоне</h1>
        <p className="muted">
          Считайте смету по голосу, ведите стройплощадки и бригаду в одном месте —
          без Excel и бумажных блокнотов.
        </p>
        <div className="row-actions">
          <Link className="button" href="/login">Попробовать</Link>
          <a className="button secondary" href="#features">Возможности</a>
        </div>
      </section>

      <section className="card" id="features">
        <div className="group-title">
          <h2>Что умеет ProrabTask</h2>
        </div>
        <div className="list">
          {FEATURES.map((f) => (
            <div className="row" key={f.title}>
              <strong>{f.title}</strong>
              <span className="muted">{f.text}</span>
            </div>
          ))}
        </div>
        <div className="actions">
          <Link className="button" href="/login">Попробовать</Link>
        </div>
      </section>

      <section className="card" id="how">
        <div className="group-title">
          <h2>Как это работает</h2>
        </div>
        <div className="list">
          {STEPS.map((s, i) => (
            <div className="row" key={s.title}>
              <strong>{i + 1}. {s.title}</strong>
              <span className="muted">{s.text}</span>
            </div>
          ))}
        </div>
        <div className="actions">
          <Link className="button" href="/login">Попробовать</Link>
        </div>
      </section>

      <section className="card" id="faq">
        <div className="group-title">
          <h2>Частые вопросы</h2>
        </div>
        <div className="list">
          {FAQ.map((item) => (
            <details className="manage" key={item.q}>
              <summary>{item.q}</summary>
              <p className="muted">{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Готовы навести порядок на объектах?</h2>
        <p className="muted">Зайдите в ProrabTask и соберите первый объект, задачи и смету за несколько минут.</p>
        <div className="actions">
          <Link className="button" href="/login">Попробовать</Link>
        </div>
      </section>

      <section className="card" id="privacy">
        <div className="group-title">
          <h2>Обработка данных и конфиденциальность</h2>
        </div>
        <div className="list">
          <p className="muted">
            Используя Telegram-бота и приложение ProrabTask («Сервис»), вы соглашаетесь
            с настоящими условиями обработки персональных данных.
          </p>

          <details className="manage">
            <summary>Какие данные мы собираем</summary>
            <p className="muted">
              Telegram ID, имя и имя пользователя, фотография профиля, данные об объектах, задачах, сметах и
              фотографиях, которые вы добавляете в Сервис, а также технические данные для входа без пароля (passkey).
            </p>
          </details>

          <details className="manage">
            <summary>Как мы используем данные</summary>
            <p className="muted">
              Данные используются только для работы Сервиса: формирования смет, ведения объектов и задач,
              авторизации и уведомлений. Мы не продаём ваши данные и не передаём их третьим лицам для рекламы.
            </p>
          </details>

          <details className="manage">
            <summary>Где хранятся данные</summary>
            <p className="muted">
              Данные хранятся в базе данных Supabase. Платежи по подписке обрабатываются платёжным сервисом —
              Сервис не хранит данные вашей банковской карты. Для формирования смет текст и голосовые описания
              могут передаваться ИИ-провайдеру.
            </p>
          </details>

          <details className="manage">
            <summary>Как удалить данные</summary>
            <p className="muted">
              Объекты и задачи можно удалить в приложении. Для полного удаления аккаунта и связанных данных
              обратитесь к администратору сервиса — мы удалим данные по вашему запросу.
            </p>
          </details>

          <details className="manage">
            <summary>Контакты по вопросам данных</summary>
            <p className="muted">
              По вопросам обработки персональных данных пишите администратору сервиса через бота.
            </p>
          </details>
        </div>
      </section>
    </main>
  );
}

/* omni_hud.so: contador de FPS, temperatura e bateria por cima dos ports (LD_PRELOAD).
 *
 * Intercepta eglSwapBuffers (direto, por dlsym ou por eglGetProcAddress) e, antes de
 * cada quadro ir para a tela, desenha uma pílula no canto com GLES2. Guarda e devolve
 * o estado do GL que mexe, então o jogo não percebe.
 *
 * Controlado por arquivos em /dev/shm (escritos pelo omni_atalho.py):
 *   omni36os-hud     "1" mostra o contador; "2" também a frequência do processador e da GPU
 *   omni36os-fpscap  N > 0 limita o jogo a N quadros/s (economiza bateria)
 *   omni36os-shot    um número; quando muda, salva a tela em <pasta do jogo>/imagens
 *
 * Sem headers do sistema: o cross-compilador do PC não tem sysroot. As funções da libc
 * são declaradas aqui e resolvidas quando a biblioteca carrega.
 */

typedef unsigned long size_t;
typedef long ssize_t;
struct timespec { long tv_sec; long tv_nsec; };

extern int open(const char *, int, ...);
extern ssize_t read(int, void *, size_t);
extern ssize_t write(int, const void *, size_t);
extern int close(int);
extern int mkdir(const char *, unsigned);
extern int snprintf(char *, size_t, const char *, ...);
extern int strcmp(const char *, const char *);
extern void *malloc(size_t);
extern void free(void *);
extern int clock_gettime(int, struct timespec *);
extern int nanosleep(const struct timespec *, struct timespec *);
extern long time(long *);
extern void *localtime_r(const long *, void *);
extern size_t strftime(char *, size_t, const char *, const void *);
extern void *dlopen(const char *, int);
extern void *dlvsym(void *, const char *, const char *);
extern char *program_invocation_short_name;
extern char *getenv(const char *);

#define RTLD_LAZY 1
#define RTLD_NEXT ((void *)-1l)
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 0100
#define O_TRUNC 01000
#define CLOCK_MONOTONIC 1

/* --- dlsym verdadeiro (o nosso intercepta) --- */

typedef void *(*dlsym_fn)(void *, const char *);
static dlsym_fn real_dlsym;

static void *rdlsym(void *h, const char *n)
{
    if (!real_dlsym) {
        static const char *vers[] = {"GLIBC_2.34", "GLIBC_2.17", "GLIBC_2.4", "GLIBC_2.2.5", 0};   /* 2.17: aarch64, 2.4: armhf */
        for (int i = 0; vers[i] && !real_dlsym; i++)
            real_dlsym = (dlsym_fn)dlvsym(RTLD_NEXT, "dlsym", vers[i]);
        if (!real_dlsym)
            return 0;
    }
    return real_dlsym(h, n);
}

/* --- EGL e GLES2 --- */

typedef unsigned (*swap_fn)(void *, void *);
typedef void *(*gpa_fn)(const char *);
static swap_fn real_swap;
static gpa_fn real_gpa;
static void *libegl, *libgles;

static void *egl(const char *n)
{
    if (!libegl)
        libegl = dlopen("libEGL.so.1", RTLD_LAZY);
    void *p = libegl ? rdlsym(libegl, n) : 0;
    return p ? p : rdlsym(RTLD_NEXT, n);
}

static void *gl(const char *n)
{
    if (!libgles)
        libgles = dlopen("libGLESv2.so.2", RTLD_LAZY);
    void *p = libgles ? rdlsym(libgles, n) : 0;
    if (!p && real_gpa)
        p = real_gpa(n);
    return p;
}

typedef unsigned GLuint;
typedef int GLint;
typedef unsigned GLenum;
typedef unsigned char GLboolean;

static struct {
    void *ctx;
    int ok, es3;
    GLuint prog;
    GLint u_size, u_rect, u_rad, u_mode;
    void (*GetIntegerv)(GLenum, GLint *);
    GLboolean (*IsEnabled)(GLenum);
    void (*Enable)(GLenum), (*Disable)(GLenum);
    void (*BlendFuncSeparate)(GLenum, GLenum, GLenum, GLenum);
    void (*BlendEquationSeparate)(GLenum, GLenum);
    void (*ColorMask)(GLboolean, GLboolean, GLboolean, GLboolean);
    void (*GetBooleanv)(GLenum, GLboolean *);
    void (*Viewport)(GLint, GLint, GLint, GLint);
    void (*UseProgram)(GLuint);
    void (*BindBuffer)(GLenum, GLuint);
    void (*BindFramebuffer)(GLenum, GLuint);
    void (*BindVertexArray)(GLuint);
    void (*EnableVertexAttribArray)(GLuint), (*DisableVertexAttribArray)(GLuint);
    void (*VertexAttribPointer)(GLuint, GLint, GLenum, GLboolean, GLint, const void *);
    void (*GetVertexAttribiv)(GLuint, GLenum, GLint *);
    void (*GetVertexAttribPointerv)(GLuint, GLenum, void **);
    void (*Uniform2f)(GLint, float, float);
    void (*Uniform4f)(GLint, float, float, float, float);
    void (*Uniform1f)(GLint, float);
    void (*DrawArrays)(GLenum, GLint, GLint);
    void (*ReadPixels)(GLint, GLint, GLint, GLint, GLenum, GLenum, void *);
    void (*PixelStorei)(GLenum, GLint);
    GLenum (*GetError)(void);
} G;

static void *(*eglGetCurrentContext_)(void);
static unsigned (*eglQuerySurface_)(void *, void *, GLint, GLint *);
static unsigned (*eglQueryContext_)(void *, void *, GLint, GLint *);

static const char *VS =
    "attribute vec2 aP; attribute vec4 aC; uniform vec2 uS; varying vec4 vC;\n"
    "void main(){ vC = aC; gl_Position = vec4(aP.x / uS.x * 2.0 - 1.0, 1.0 - aP.y / uS.y * 2.0, 0.0, 1.0); }\n";
/* uMode 1: pílula de cantos redondos (distância até o retângulo, borda suave) */
static const char *FS =
    "precision mediump float; varying vec4 vC; uniform vec4 uR; uniform float uRad; uniform float uM;\n"
    "void main(){ float a = 1.0;\n"
    "  if (uM > 0.5) { vec2 p = gl_FragCoord.xy - (uR.xy + uR.zw * 0.5);\n"
    "    vec2 q = abs(p) - uR.zw * 0.5 + uRad;\n"
    "    float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - uRad;\n"
    "    a = clamp(0.5 - d, 0.0, 1.0); }\n"
    "  gl_FragColor = vec4(vC.rgb, vC.a * a); }\n";

static GLuint shader(GLenum type, const char *src)
{
    GLuint (*CreateShader)(GLenum) = gl("glCreateShader");
    void (*ShaderSource)(GLuint, GLint, const char **, const GLint *) = gl("glShaderSource");
    void (*CompileShader)(GLuint) = gl("glCompileShader");
    void (*GetShaderiv)(GLuint, GLenum, GLint *) = gl("glGetShaderiv");
    if (!CreateShader || !ShaderSource || !CompileShader || !GetShaderiv)
        return 0;
    GLuint s = CreateShader(type);
    GLint ok = 0;
    ShaderSource(s, 1, &src, 0);
    CompileShader(s);
    GetShaderiv(s, 0x8B81, &ok);
    return ok ? s : 0;
}

static int gl_init(void)
{
#define L(f) if (!(G.f = gl("gl" #f))) return 0
    L(GetIntegerv); L(IsEnabled); L(Enable); L(Disable); L(BlendFuncSeparate); L(BlendEquationSeparate);
    L(ColorMask); L(GetBooleanv); L(Viewport); L(UseProgram); L(BindBuffer); L(BindFramebuffer);
    L(EnableVertexAttribArray); L(DisableVertexAttribArray); L(VertexAttribPointer); L(GetVertexAttribiv);
    L(GetVertexAttribPointerv); L(Uniform2f); L(Uniform4f); L(Uniform1f); L(DrawArrays); L(ReadPixels);
    L(PixelStorei); L(GetError);
#undef L
    G.BindVertexArray = gl("glBindVertexArray");
    GLuint vs = shader(0x8B31, VS), fs = shader(0x8B30, FS);
    GLuint (*CreateProgram)(void) = gl("glCreateProgram");
    void (*AttachShader)(GLuint, GLuint) = gl("glAttachShader");
    void (*BindAttribLocation)(GLuint, GLuint, const char *) = gl("glBindAttribLocation");
    void (*LinkProgram)(GLuint) = gl("glLinkProgram");
    void (*GetProgramiv)(GLuint, GLenum, GLint *) = gl("glGetProgramiv");
    GLint (*GetUniformLocation)(GLuint, const char *) = gl("glGetUniformLocation");
    if (!vs || !fs || !CreateProgram || !AttachShader || !BindAttribLocation || !LinkProgram || !GetProgramiv ||
        !GetUniformLocation)
        return 0;
    GLint ok = 0;
    G.prog = CreateProgram();
    AttachShader(G.prog, vs);
    AttachShader(G.prog, fs);
    BindAttribLocation(G.prog, 0, "aP");
    BindAttribLocation(G.prog, 1, "aC");
    LinkProgram(G.prog);
    GetProgramiv(G.prog, 0x8B82, &ok);
    if (!ok)
        return 0;
    G.u_size = GetUniformLocation(G.prog, "uS");
    G.u_rect = GetUniformLocation(G.prog, "uR");
    G.u_rad = GetUniformLocation(G.prog, "uRad");
    G.u_mode = GetUniformLocation(G.prog, "uM");
    return 1;
}

/* --- arquivos pequenos --- */

static int read_small(const char *path, char *buf, int n)
{
    int fd = open(path, O_RDONLY), k;
    if (fd < 0)
        return -1;
    k = (int)read(fd, buf, n - 1);
    close(fd);
    if (k < 0)
        k = 0;
    buf[k] = 0;
    return k;
}

static long read_num(const char *path, long dflt)
{
    char b[32];
    long v = 0;
    int neg = 0, any = 0;
    if (read_small(path, b, sizeof b) <= 0)
        return dflt;
    for (char *p = b; *p; p++) {
        if (*p == '-' && !any)
            neg = 1;
        else if (*p >= '0' && *p <= '9')
            v = v * 10 + (*p - '0'), any = 1;
        else if (any)
            break;
    }
    return any ? (neg ? -v : v) : dflt;
}

static double now(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

/* --- fonte 5x7 (linhas de cima para baixo, bit 4 = coluna da esquerda) --- */

static const unsigned char *glyph(char c)
{
    static const unsigned char D[10][7] = {
        {14, 17, 19, 21, 25, 17, 14}, {4, 12, 4, 4, 4, 4, 14}, {14, 17, 1, 2, 4, 8, 31},
        {31, 2, 4, 2, 1, 17, 14}, {2, 6, 10, 18, 31, 2, 2}, {31, 16, 30, 1, 1, 17, 14},
        {6, 8, 16, 30, 17, 17, 14}, {31, 1, 2, 4, 8, 8, 8}, {14, 17, 17, 14, 17, 17, 14},
        {14, 17, 17, 15, 1, 2, 12}};
    static const struct { char c; unsigned char b[7]; } X[] = {
        {'A', {14, 17, 17, 31, 17, 17, 17}}, {'C', {14, 17, 16, 16, 16, 17, 14}},
        {'F', {31, 16, 16, 30, 16, 16, 16}}, {'G', {14, 17, 16, 23, 17, 17, 15}}, {'L', {16, 16, 16, 16, 16, 16, 31}},
        {'P', {30, 17, 17, 30, 16, 16, 16}}, {'R', {30, 17, 17, 30, 20, 18, 17}},
        {'S', {15, 16, 16, 14, 1, 1, 30}}, {'T', {31, 4, 4, 4, 4, 4, 4}},
        {'U', {17, 17, 17, 17, 17, 17, 14}}, {'V', {17, 17, 17, 17, 17, 10, 4}},
        {'%', {24, 25, 2, 4, 8, 19, 3}}, {'^', {12, 18, 18, 12, 0, 0, 0}},        /* ^ = grau */
        {'[', {4, 10, 10, 10, 14, 31, 14}},                                        /* termômetro */
        {']', {14, 27, 17, 17, 17, 17, 31}},                                       /* bateria */
        {'~', {2, 4, 8, 31, 2, 4, 8}},                                             /* raio: carregando */
        {'-', {0, 0, 0, 31, 0, 0, 0}}};
    if (c >= '0' && c <= '9')
        return D[c - '0'];
    for (unsigned i = 0; i < sizeof X / sizeof X[0]; i++)
        if (X[i].c == c)
            return X[i].b;
    return 0;
}

/* --- desenho: triângulos com posição (px) e cor --- */

#define MAXV 9000
static float V[MAXV * 6];
static int nv;

static void quad(float x, float y, float w, float h, const float *c)
{
    if (nv + 6 > MAXV)
        return;
    float xs[6] = {x, x + w, x, x + w, x + w, x}, ys[6] = {y, y, y + h, y, y + h, y + h};
    for (int i = 0; i < 6; i++) {
        float *v = V + (nv++) * 6;
        v[0] = xs[i], v[1] = ys[i], v[2] = c[0], v[3] = c[1], v[4] = c[2], v[5] = c[3];
    }
}

static float text_w(const char *s, float px)
{
    int n = 0;
    while (s[n])
        n++;
    return n ? (n * 6 - 1) * px : 0;
}

static float text(const char *s, float x, float y, float px, const float *c)
{
    for (; *s; s++, x += 6 * px) {
        const unsigned char *g = glyph(*s);
        for (int r = 0; g && r < 7; r++)
            for (int k = 0; k < 5; k++)
                if (g[r] & (16 >> k))
                    quad(x + k * px, y + r * px, px, px, c);
    }
    return x;
}

/* --- estado do HUD --- */

static struct {
    double t0, last_frame, flags_at, sens_at, toast_until;
    int frames, fps, temp, bat, charging, show, clk, cpu, gpu, cap;
    double clk_at;
    long shot_seen;
    int shot_init;
} H = {.fps = -1};

static const float WHITE[4] = {0.95f, 0.96f, 1.0f, 1.0f}, DIM[4] = {0.62f, 0.66f, 0.78f, 1.0f},
                   GREEN[4] = {0.30f, 0.88f, 0.55f, 1.0f}, YELLOW[4] = {0.98f, 0.78f, 0.25f, 1.0f},
                   RED[4] = {0.97f, 0.45f, 0.45f, 1.0f}, BG[4] = {0.05f, 0.06f, 0.12f, 0.78f},
                   LINE[4] = {1.0f, 1.0f, 1.0f, 0.14f}, ACCENT[4] = {0.75f, 0.52f, 0.99f, 1.0f};

static void poll_flags(double t)
{
    char b[16];
    if (t - H.flags_at < 0.5)
        return;
    H.flags_at = t;
    H.show = read_small("/dev/shm/omni36os-hud", b, sizeof b) > 0 && (b[0] == '1' || b[0] == '2');
    H.clk = H.show && b[0] == '2';
    if (H.clk && t - H.clk_at >= 1.0) {          /* MHz atuais (o processador Automático muda) */
        H.clk_at = t;
        H.cpu = (int)(read_num("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq", 0) / 1000);
        H.gpu = (int)(read_num("/sys/class/devfreq/ff400000.gpu/cur_freq", 0) / 1000000);
    }
    H.cap = (int)read_num("/dev/shm/omni36os-fpscap", 0);
    if (t - H.sens_at >= 2.0 || H.sens_at == 0) {
        H.sens_at = t;
        H.temp = (int)(read_num("/sys/class/thermal/thermal_zone0/temp", 0) / 1000);
        H.bat = (int)read_num("/sys/class/power_supply/battery/capacity", -1);
        H.charging = read_small("/sys/class/power_supply/battery/status", b, sizeof b) > 0 && b[0] == 'C';
    }
}

static int want_shot(void)
{
    long v = read_num("/dev/shm/omni36os-shot", 0);
    if (!H.shot_init) {
        H.shot_init = 1, H.shot_seen = v;
        return 0;
    }
    if (v == H.shot_seen)
        return 0;
    H.shot_seen = v;
    return 1;
}

static void save_shot(int w, int h)
{
    unsigned char *px = malloc((size_t)w * h * 4 + 54);
    if (!px)
        return;
    unsigned char *img = px + 54;
    GLint pack = 4, pbo = 0;
    G.GetIntegerv(0x0D05, &pack);
    G.PixelStorei(0x0D05, 4);
    if (G.es3) {
        G.GetIntegerv(0x88ED, &pbo);
        if (pbo)
            G.BindBuffer(0x88EB, 0);
    }
    G.ReadPixels(0, 0, w, h, 0x1908, 0x1401, img);     /* de baixo para cima: igual ao BMP */
    if (pbo)
        G.BindBuffer(0x88EB, pbo);
    G.PixelStorei(0x0D05, pack);
    for (long i = 0; i < (long)w * h; i++) {              /* RGBA -> BGRA */
        unsigned char t = img[i * 4];
        img[i * 4] = img[i * 4 + 2], img[i * 4 + 2] = t, img[i * 4 + 3] = 255;
    }
    unsigned size = 54 + (unsigned)w * h * 4;
    unsigned char hd[54] = {'B', 'M'};
#define P32(o, v) (hd[o] = (v) & 255, hd[o + 1] = ((v) >> 8) & 255, hd[o + 2] = ((v) >> 16) & 255, hd[o + 3] = ((v) >> 24) & 255)
    P32(2, size); P32(10, 54); P32(14, 40); P32(18, w); P32(22, h);
    hd[26] = 1, hd[28] = 32;
    P32(34, (unsigned)w * h * 4);
#undef P32
    for (int i = 0; i < 54; i++)
        px[i] = hd[i];
    char dir[256], name[400], stamp[40], tmbuf[128];
    long tt = time(0);
    /* na pasta do jogo (o launch-direct.sh exporta OMNI_GAME_DIR); sem ela, na pasta atual */
    const char *gd = getenv("OMNI_HUD_DIR") ? getenv("OMNI_HUD_DIR") : getenv("OMNI_GAME_DIR");
    int fd;
    snprintf(dir, sizeof dir, "%s/imagens", gd && *gd ? gd : ".");
    mkdir(dir, 0777);
    localtime_r(&tt, tmbuf);
    strftime(stamp, sizeof stamp, "%Y%m%d-%H%M%S", tmbuf);
    snprintf(name, sizeof name, "%s/%s-%s.bmp", dir, program_invocation_short_name ? program_invocation_short_name : "port",
             stamp);
    fd = open(name, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (fd >= 0) {
        long left = size, off = 0;
        while (left > 0) {
            long k = write(fd, px + off, left);
            if (k <= 0)
                break;
            off += k, left -= k;
        }
        close(fd);
        H.toast_until = now() + 2.0;
    }
    free(px);
}

static void build(int W, int Hh)
{
    float px = Hh >= 720 ? 3 : Hh >= 400 ? 2 : 1, pad = 5 * px, gap = 6 * px;
    float x = 8 * px / 2 + 4, y = 8 * px / 2 + 4, h = 7 * px + pad * 2;
    char a[16], b[16], c[16];
    const float *fc = H.fps >= 50 ? GREEN : H.fps >= 28 ? YELLOW : RED;
    const float *tc = H.temp >= 75 ? RED : H.temp >= 65 ? YELLOW : WHITE;
    const float *bc = H.charging ? GREEN : H.bat >= 0 && H.bat <= 15 ? RED : H.bat <= 30 ? YELLOW : WHITE;
    nv = 0;
    if (H.show) {
        if (H.fps >= 0)
            snprintf(a, sizeof a, "%d", H.fps);
        else
            snprintf(a, sizeof a, "--");
        snprintf(b, sizeof b, "%d^", H.temp);
        if (H.bat >= 0)
            snprintf(c, sizeof c, "%d%%", H.bat);
        else
            snprintf(c, sizeof c, "--");
        float w = pad + text_w(a, px) + px * 3 + text_w("FPS", px) + gap * 2 + px +
                  text_w("[", px) + px * 2 + text_w(b, px) + gap * 2 + px +
                  text_w(H.charging ? "~" : "]", px) + px * 2 + text_w(c, px) + pad;
        if (H.cap > 0)
            w += gap + text_w("-", px) + px;
        quad(x, y, w, h, BG);                       /* desenhado à parte, com cantos redondos */
        float cx = x + pad, ty = y + pad;
        cx = text(a, cx, ty, px, fc) + px * 2;
        cx = text("FPS", cx, ty, px, DIM) - px;
        if (H.cap > 0)
            cx = text("-", cx + gap, ty, px, ACCENT) - px;   /* limite ligado */
        cx += gap;
        quad(cx, y + pad - px, px, h - 2 * pad + 2 * px, LINE);
        cx += px + gap;
        cx = text("[", cx, ty, px, tc) + px * 2;
        cx = text(b, cx, ty, px, tc) - px + gap;
        quad(cx, y + pad - px, px, h - 2 * pad + 2 * px, LINE);
        cx += px + gap;
        cx = text(H.charging ? "~" : "]", cx, ty, px, bc) + px * 2;
        text(c, cx, ty, px, bc);
        if (H.clk) {                                /* segunda pílula: CPU e GPU em MHz */
            snprintf(a, sizeof a, "%d", H.cpu);
            snprintf(b, sizeof b, "%d", H.gpu);
            float y2 = y + h + gap;
            w = pad + text_w("CPU", px) + px * 3 + text_w(a, px) + gap * 2 + px +
                text_w("GPU", px) + px * 3 + text_w(b, px) + pad;
            quad(x, y2, w, h, BG);
            cx = text("CPU", x + pad, y2 + pad, px, DIM) + px * 2;
            cx = text(a, cx, y2 + pad, px, WHITE) - px + gap;
            quad(cx, y2 + pad - px, px, h - 2 * pad + 2 * px, LINE);
            cx += px + gap;
            cx = text("GPU", cx, y2 + pad, px, DIM) + px * 2;
            text(b, cx, y2 + pad, px, WHITE);
        }
    }
    if (now() < H.toast_until) {
        const char *msg = "CAPTURA SALVA";
        float w = text_w(msg, px) + pad * 2, tx = W - w - 8, tyy = y;
        quad(tx, tyy, w, h, BG);
        text(msg, tx + pad, tyy + pad, px, GREEN);
    }
    (void)W;
}

static void draw(int W, int Hh)
{
    if (!nv)
        return;
    GLint prog, abuf, fb, rfb = 0, vao = 0, vp[4], bsrc, bdst, basrc, badst, beq, beqa;
    GLboolean cm[4];
    GLint en[2], sz[2], ty[2], nm[2], st[2], bb[2];
    void *ptr[2];
    int blend = G.IsEnabled(0x0BE2), depth = G.IsEnabled(0x0B71), sc = G.IsEnabled(0x0C11),
        cull = G.IsEnabled(0x0B44), sten = G.IsEnabled(0x0B90);
    G.GetIntegerv(0x8B8D, &prog);
    G.GetIntegerv(0x8894, &abuf);
    G.GetIntegerv(0x8CA6, &fb);
    if (G.es3 && G.BindVertexArray) {
        G.GetIntegerv(0x85B5, &vao);
        G.GetIntegerv(0x8CAA, &rfb);
        if (vao)
            G.BindVertexArray(0);
    }
    G.GetIntegerv(0x0BA2, vp);
    G.GetIntegerv(0x80C9, &bsrc); G.GetIntegerv(0x80C8, &bdst);
    G.GetIntegerv(0x80CB, &basrc); G.GetIntegerv(0x80CA, &badst);
    G.GetIntegerv(0x8009, &beq); G.GetIntegerv(0x883D, &beqa);
    G.GetBooleanv(0x0C23, cm);
    for (int i = 0; i < 2; i++) {
        G.GetVertexAttribiv(i, 0x8622, &en[i]); G.GetVertexAttribiv(i, 0x8623, &sz[i]);
        G.GetVertexAttribiv(i, 0x8625, &ty[i]); G.GetVertexAttribiv(i, 0x886A, &nm[i]);
        G.GetVertexAttribiv(i, 0x8624, &st[i]); G.GetVertexAttribiv(i, 0x889F, &bb[i]);
        G.GetVertexAttribPointerv(i, 0x8645, &ptr[i]);
    }

    G.BindFramebuffer(0x8D40, 0);
    G.Viewport(0, 0, W, Hh);
    G.Enable(0x0BE2);
    G.BlendFuncSeparate(0x0302, 0x0303, 1, 0x0303);
    G.BlendEquationSeparate(0x8006, 0x8006);
    G.Disable(0x0B71); G.Disable(0x0C11); G.Disable(0x0B44); G.Disable(0x0B90);
    G.ColorMask(1, 1, 1, 1);
    G.UseProgram(G.prog);
    G.BindBuffer(0x8892, 0);
    G.Uniform2f(G.u_size, (float)W, (float)Hh);
    G.EnableVertexAttribArray(0);
    G.EnableVertexAttribArray(1);
    G.VertexAttribPointer(0, 2, 0x1406, 0, 24, V);
    G.VertexAttribPointer(1, 4, 0x1406, 0, 24, V + 2);
    /* fundos (os quads de cor BG) com cantos redondos, um por vez; o resto num desenho só */
    for (int q = 0; q < nv; q += 6) {
        float *v = V + q * 6;
        if (v[5] == BG[3] && v[2] == BG[0]) {
            float x = v[0], y = v[1], w = V[(q + 1) * 6] - x, h = V[(q + 2) * 6 + 1] - y;
            G.Uniform1f(G.u_mode, 1);
            G.Uniform4f(G.u_rect, x, Hh - y - h, w, h);
            G.Uniform1f(G.u_rad, h / 2);
            G.DrawArrays(4, q, 6);
        }
    }
    G.Uniform1f(G.u_mode, 0);
    for (int q = 0; q < nv; q += 6) {               /* trechos seguidos sem fundo */
        int e = q;
        while (e < nv && !(V[e * 6 + 5] == BG[3] && V[e * 6 + 2] == BG[0]))
            e += 6;
        if (e > q)
            G.DrawArrays(4, q, e - q);
        q = e;
    }

    for (int i = 0; i < 2; i++) {
        G.BindBuffer(0x8892, bb[i]);
        G.VertexAttribPointer(i, sz[i], ty[i], nm[i], st[i], ptr[i]);
        if (!en[i])
            G.DisableVertexAttribArray(i);
    }
    G.BindBuffer(0x8892, abuf);
    G.UseProgram(prog);
    G.ColorMask(cm[0], cm[1], cm[2], cm[3]);
    G.BlendEquationSeparate(beq, beqa);
    G.BlendFuncSeparate(bsrc, bdst, basrc, badst);
    (blend ? G.Enable : G.Disable)(0x0BE2);
    if (depth) G.Enable(0x0B71);
    if (sc) G.Enable(0x0C11);
    if (cull) G.Enable(0x0B44);
    if (sten) G.Enable(0x0B90);
    G.Viewport(vp[0], vp[1], vp[2], vp[3]);
    if (G.es3) {
        G.BindFramebuffer(0x8CA9, fb);
        G.BindFramebuffer(0x8CA8, rfb);
        if (vao && G.BindVertexArray)
            G.BindVertexArray(vao);
    } else {
        G.BindFramebuffer(0x8D40, fb);
    }
    while (G.GetError())      /* erros nossos não podem aparecer para o jogo */
        ;
}

/* FPS do jogo para o modo automático do processador (omni_cpuauto.py): o arquivo novo
 * diz que há um jogo desenhando; parado há mais de 2 s, não há. */
static void publish_fps(void)
{
    char b[16];
    int n = snprintf(b, sizeof b, "%d\n", H.fps);
    /* sem O_CREAT primeiro: o serviço de atalhos já cria o arquivo 0666, e o protected_regular
     * do /dev/shm recusa O_CREAT em arquivo de outro dono */
    int fd = open("/dev/shm/omni36os-fps", O_WRONLY | O_TRUNC);
    if (fd < 0)
        fd = open("/dev/shm/omni36os-fps", O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (fd >= 0) {
        write(fd, b, n);
        close(fd);
    }
}

static void frame(void *dpy, void *surf)
{
    double t = now();
    if (!H.t0)
        H.t0 = t;
    H.frames++;
    if (t - H.t0 >= 0.5) {
        H.fps = (int)(H.frames / (t - H.t0) + 0.5);
        H.frames = 0, H.t0 = t;
        publish_fps();
    }
    poll_flags(t);
    int shot = want_shot();
    if (!H.show && !shot && t >= H.toast_until)
        return;
    if (!eglGetCurrentContext_) {
        eglGetCurrentContext_ = egl("eglGetCurrentContext");
        eglQuerySurface_ = egl("eglQuerySurface");
        eglQueryContext_ = egl("eglQueryContext");
        if (!eglGetCurrentContext_ || !eglQuerySurface_ || !eglQueryContext_)
            return;
    }
    void *ctx = eglGetCurrentContext_();
    if (!ctx)
        return;
    if (ctx != G.ctx) {                              /* contexto novo: programa novo */
        GLint ver = 0, type = 0;
        G.ctx = ctx;
        eglQueryContext_(dpy, ctx, 0x3097, &type);   /* só GLES 2 ou mais novo */
        eglQueryContext_(dpy, ctx, 0x3098, &ver);
        G.ok = type == 0x30A0 && ver >= 2 && gl_init();
        G.es3 = ver >= 3;
    }
    if (!G.ok)
        return;
    GLint w = 0, h = 0;
    eglQuerySurface_(dpy, surf, 0x3057, &w);
    eglQuerySurface_(dpy, surf, 0x3056, &h);
    if (w <= 0 || h <= 0)
        return;
    if (shot)
        save_shot(w, h);                            /* antes do HUD: a foto sai limpa */
    build(w, h);
    draw(w, h);
}

static void cap_sleep(void)
{
    if (H.cap <= 0) {
        H.last_frame = 0;
        return;
    }
    double t = now(), want = 1.0 / H.cap;
    if (H.last_frame && t - H.last_frame < want) {
        double d = want - (t - H.last_frame);
        struct timespec s = {(long)d, (long)((d - (long)d) * 1e9)};
        nanosleep(&s, 0);
        t = now();
    }
    H.last_frame = t;
}

/* --- pontos de entrada interceptados --- */

unsigned eglSwapBuffers(void *dpy, void *surf)
{
    if (!real_swap)
        real_swap = (swap_fn)rdlsym(RTLD_NEXT, "eglSwapBuffers");
    if (!real_swap)
        real_swap = (swap_fn)egl("eglSwapBuffers");
    if (!real_swap)
        return 0;
    frame(dpy, surf);
    cap_sleep();
    return real_swap(dpy, surf);
}

void *eglGetProcAddress(const char *name)
{
    if (!real_gpa)
        real_gpa = (gpa_fn)rdlsym(RTLD_NEXT, "eglGetProcAddress");
    if (!real_gpa)
        real_gpa = (gpa_fn)egl("eglGetProcAddress");
    if (name && !strcmp(name, "eglSwapBuffers")) {
        if (!real_swap && real_gpa)
            real_swap = (swap_fn)real_gpa(name);
        return (void *)eglSwapBuffers;
    }
    return real_gpa ? real_gpa(name) : 0;
}

void *dlsym(void *h, const char *name)
{
    void *p = rdlsym(h, name);
    if (!p || !name)
        return p;
    if (!strcmp(name, "eglSwapBuffers")) {
        if (!real_swap)
            real_swap = (swap_fn)p;
        /* outro eglSwapBuffers (ex.: o glvnd buscando o do driver): não intercepta duas vezes */
        return p == (void *)real_swap ? (void *)eglSwapBuffers : p;
    }
    if (!strcmp(name, "eglGetProcAddress")) {
        if (!real_gpa)
            real_gpa = (gpa_fn)p;
        return (void *)eglGetProcAddress;
    }
    return p;
}

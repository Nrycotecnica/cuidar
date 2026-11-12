// ---------------------------------------------------------------------------
//  LKI INDUSTRIAL - instalador (.exe de um arquivo so)
//  Desenvolvido por Diego Pereira
// ---------------------------------------------------------------------------
//  O pacote inteiro (Python embutido + sistema + telas) vai DENTRO deste .exe:
//  instala sem internet, sem Docker e sem administrador, em
//  %LOCALAPPDATA%\LkiIndustrial. O trabalho pesado e feito pelos mesmos
//  scripts PowerShell que o GitHub testa num Windows real a cada versao
//  (instalar.ps1 / atualizar.ps1); este programa e a cara deles.
//
//  O QUE ELE FAZ
//    - Nao instalado: pede e-mail e senha do administrador e instala.
//    - Ja instalado: atualiza para a versao embutida (com backup e volta
//      atras automatica), sem tocar nos dados.
//    - No fim, se marcado, libera a porta do sistema no firewall SO PARA A
//      REDE LOCAL. E o unico passo que pede administrador: o Windows mostra o
//      "Sim" uma vez. Quem clicar "Nao" instala do mesmo jeito e pode liberar
//      depois pelo atalho LIBERAR REDE LKI INDUSTRIAL.
//
//  Modo sem janela (testes automatizados):
//    LKI-INDUSTRIAL-Instalador.exe /silencioso /email:x /senha:y [/firewall]
//
//  Compilado pelo csc.exe do .NET Framework 4 que ja vem no Windows (C# 5:
//  nada de interpolacao de string ou recursos novos).
// ---------------------------------------------------------------------------
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace LkiIndustrial
{
    static class Instalador
    {
        static readonly string Raiz = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LkiIndustrial");
        static string Ferramentas { get { return Path.Combine(Raiz, "ferramentas"); } }
        static bool JaInstalado { get { return File.Exists(Path.Combine(Raiz, "programa\\python\\python.exe")); } }

        static Form janela;
        static TextBox txtEmail, txtSenha, txtSenha2, txtLog;
        static CheckBox chkRede;
        static Button botao;
        static ProgressBar barra;
        static Label lblEtapa;
        static string urlFinal = "http://127.0.0.1:8080";
        static bool concluido;
        static bool silencioso;
        static StreamWriter logArquivo;

        [STAThread]
        static int Main(string[] args)
        {
            Dictionary<string, string> op = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (string a in args)
            {
                string s = a.TrimStart('/', '-');
                int i = s.IndexOf(':');
                if (i > 0) op[s.Substring(0, i)] = s.Substring(i + 1); else op[s] = "1";
            }
            if (op.ContainsKey("silencioso"))
            {
                silencioso = true;
                string email = op.ContainsKey("email") ? op["email"] : "";
                string senha = op.ContainsKey("senha") ? op["senha"] : "";
                return Executar(email, senha, op.ContainsKey("firewall")) ? 0 : 1;
            }
            Application.EnableVisualStyles();
            MontarJanela();
            Application.Run(janela);
            return 0;
        }

        // ------------------------------------------------------------------ janela
        static void MontarJanela()
        {
            Color azul = Color.FromArgb(29, 63, 96);
            janela = new Form();
            janela.Text = "LKI INDUSTRIAL - Instalador";
            janela.ClientSize = new Size(560, 520);
            janela.FormBorderStyle = FormBorderStyle.FixedDialog;
            janela.MaximizeBox = false;
            janela.StartPosition = FormStartPosition.CenterScreen;
            janela.BackColor = Color.White;
            janela.Font = new Font("Segoe UI", 9.5f);
            try { janela.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            Panel topo = new Panel();
            topo.BackColor = azul;
            topo.SetBounds(0, 0, 560, 92);
            janela.Controls.Add(topo);
            PictureBox logo = new PictureBox();
            logo.SetBounds(20, 16, 60, 60);
            logo.SizeMode = PictureBoxSizeMode.Zoom;
            try { logo.Image = new Icon(janela.Icon, 64, 64).ToBitmap(); } catch { }
            topo.Controls.Add(logo);
            topo.Controls.Add(Rotulo("LKI INDUSTRIAL", 92, 14, 440, 32, new Font("Segoe UI", 18f, FontStyle.Bold), Color.White));
            topo.Controls.Add(Rotulo("Engenharia de exaustao e ventilacao industrial", 94, 48, 440, 20, null, Color.FromArgb(210, 225, 240)));
            topo.Controls.Add(Rotulo("Desenvolvido por Diego Pereira", 94, 67, 440, 18, new Font("Segoe UI", 8.5f), Color.FromArgb(170, 195, 220)));

            int y = 108;
            if (JaInstalado)
            {
                janela.Controls.Add(Rotulo("O LKI INDUSTRIAL ja esta instalado neste computador.\r\nEste instalador vai atualiza-lo para a versao " + VersaoEmbutida() +
                    ".\r\nSeus projetos e cadastros sao mantidos (com backup antes).", 24, y, 512, 64, null, Color.Black));
                y += 76;
            }
            else
            {
                janela.Controls.Add(Rotulo("Crie o acesso do administrador do sistema:", 24, y, 512, 22, new Font("Segoe UI", 10f, FontStyle.Bold), Color.Black));
                y += 30;
                txtEmail = Campo("E-mail", ref y, false);
                txtSenha = Campo("Senha (minimo 8 caracteres)", ref y, true);
                txtSenha2 = Campo("Repita a senha", ref y, true);
            }
            chkRede = new CheckBox();
            chkRede.Text = "Permitir acesso pelos outros computadores da rede local\r\n(o Windows vai pedir permissao uma vez, so para o firewall)";
            chkRede.SetBounds(24, y, 512, 40);
            chkRede.Checked = true;
            janela.Controls.Add(chkRede);
            y += 50;

            lblEtapa = Rotulo("", 24, y, 512, 20, null, Color.FromArgb(60, 60, 60));
            janela.Controls.Add(lblEtapa);
            y += 22;
            barra = new ProgressBar();
            barra.SetBounds(24, y, 512, 14);
            barra.Maximum = 100;
            janela.Controls.Add(barra);
            y += 22;
            txtLog = new TextBox();
            txtLog.Multiline = true;
            txtLog.ReadOnly = true;
            txtLog.ScrollBars = ScrollBars.Vertical;
            txtLog.BackColor = Color.FromArgb(246, 248, 250);
            txtLog.Font = new Font("Consolas", 8.5f);
            txtLog.SetBounds(24, y, 512, 520 - y - 60);
            janela.Controls.Add(txtLog);

            botao = new Button();
            botao.Text = JaInstalado ? "Atualizar" : "Instalar";
            botao.SetBounds(396, 520 - 46, 140, 34);
            botao.BackColor = azul;
            botao.ForeColor = Color.White;
            botao.FlatStyle = FlatStyle.Flat;
            botao.Click += BotaoClick;
            janela.Controls.Add(botao);
            janela.AcceptButton = botao;
        }

        static Label Rotulo(string texto, int x, int y, int w, int h, Font f, Color cor)
        {
            Label l = new Label();
            l.Text = texto;
            l.SetBounds(x, y, w, h);
            l.ForeColor = cor;
            l.BackColor = Color.Transparent;
            if (f != null) l.Font = f;
            return l;
        }

        static TextBox Campo(string rotulo, ref int y, bool senha)
        {
            janela.Controls.Add(Rotulo(rotulo, 24, y + 3, 190, 22, null, Color.Black));
            TextBox t = new TextBox();
            t.SetBounds(220, y, 316, 26);
            t.UseSystemPasswordChar = senha;
            janela.Controls.Add(t);
            y += 34;
            return t;
        }

        static void BotaoClick(object sender, EventArgs e)
        {
            if (concluido) { AbrirNavegador(); janela.Close(); return; }
            string email = "", senha = "";
            if (!JaInstalado)
            {
                email = txtEmail.Text.Trim();
                senha = txtSenha.Text;
                if (email.IndexOf('@') < 1) { Aviso("Informe um e-mail valido."); return; }
                if (senha.Length < 8) { Aviso("A senha precisa ter pelo menos 8 caracteres."); return; }
                if (senha != txtSenha2.Text) { Aviso("As senhas nao conferem."); return; }
            }
            botao.Enabled = false;
            bool rede = chkRede.Checked;
            Thread t = new Thread(delegate ()
            {
                bool ok = Executar(email, senha, rede);
                janela.BeginInvoke((MethodInvoker)delegate
                {
                    botao.Enabled = true;
                    if (ok)
                    {
                        concluido = true;
                        botao.Text = "Abrir o sistema";
                        Etapa("Pronto! Use os atalhos LKI INDUSTRIAL na Area de Trabalho.", 100);
                    }
                    else
                    {
                        botao.Text = JaInstalado ? "Tentar de novo" : "Tentar de novo";
                    }
                });
            });
            t.IsBackground = true;
            t.Start();
        }

        static void Aviso(string m) { MessageBox.Show(janela, m, "LKI INDUSTRIAL", MessageBoxButtons.OK, MessageBoxIcon.Warning); }

        // ------------------------------------------------------------------ trabalho
        static bool Executar(string email, string senha, bool liberarRede)
        {
            string tmp = Path.Combine(Path.GetTempPath(), "lki-instalador-" + Guid.NewGuid().ToString("N"));
            try
            {
                Directory.CreateDirectory(Raiz);
                try { logArquivo = new StreamWriter(Path.Combine(Raiz, "instalador.log"), true, Encoding.UTF8); logArquivo.AutoFlush = true; } catch { }
                Log("==== " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  instalador " + VersaoEmbutida());
                Directory.CreateDirectory(tmp);
                Etapa("Preparando o pacote...", 5);
                string zip = Path.Combine(tmp, "pacote.zip");
                string man = Path.Combine(tmp, "versao.json");
                string ps1 = Path.Combine(tmp, "instalar.ps1");
                Extrair("LKI-INDUSTRIAL-windows.zip", zip);
                Extrair("versao.json", man);
                Extrair("instalar.ps1", ps1);

                // A mesma impressao digital que o atualizador confere: pacote
                // corrompido (download cortado, antivirus mexendo) nao instala.
                Etapa("Conferindo a integridade do pacote...", 15);
                string esperado = LerCampoJson(File.ReadAllText(man), "sha256").ToLowerInvariant();
                if (Sha256(zip) != esperado) { Log("ERRO: o pacote embutido esta corrompido. Baixe o instalador de novo."); Etapa("Pacote corrompido.", 0); return false; }

                int codigo;
                bool atualizacao = JaInstalado;
                if (atualizacao)
                {
                    Etapa("Atualizando (backup do banco, troca da versao)...", 30);
                    codigo = RodarPowerShell(Path.Combine(Ferramentas, "atualizar.ps1"), "-Silencioso -Pacote \"" + zip + "\" -Manifesto \"" + man + "\"", null);
                    if (codigo == 2) { Log("A versao nova nao respondeu; o sistema voltou para a anterior com os dados de antes."); Etapa("Atualizacao revertida.", 0); return false; }
                    if (codigo != 0) { Etapa("Falha na atualizacao.", 0); return false; }
                }
                else
                {
                    Etapa("Instalando (pode levar um minuto)...", 30);
                    Dictionary<string, string> env = new Dictionary<string, string>();
                    env["LKI_ADMIN_EMAIL"] = email;
                    env["LKI_ADMIN_SENHA"] = senha;
                    codigo = RodarPowerShell(ps1, "-Silencioso -Pacote \"" + zip + "\" -Manifesto \"" + man + "\"", env);
                    if (codigo != 0) { Etapa("Falha na instalacao.", 0); return false; }
                }
                Etapa("Sistema instalado e no ar.", 80);

                // Copia de si mesmo: icone em "Aplicativos instalados" e reparo futuro.
                try { File.Copy(Application.ExecutablePath, Path.Combine(Raiz, "LKI-INDUSTRIAL-Instalador.exe"), true); } catch { }

                if (liberarRede)
                {
                    Etapa("Liberando a rede local no firewall (o Windows vai pedir permissao)...", 88);
                    LiberarRede();
                }
                Etapa("Pronto!", 100);
                Log("Concluido. Endereco: " + urlFinal);
                return true;
            }
            catch (Exception ex)
            {
                Log("ERRO: " + ex.Message);
                Etapa("Ocorreu um erro. Veja o registro abaixo.", 0);
                return false;
            }
            finally
            {
                try { Directory.Delete(tmp, true); } catch { }
                if (logArquivo != null) { try { logArquivo.Close(); } catch { } logArquivo = null; }
            }
        }

        static void LiberarRede()
        {
            string script = Path.Combine(Ferramentas, "liberar-rede.ps1");
            if (!File.Exists(script)) { Log("Script de liberacao da rede nao encontrado."); return; }
            int c = RodarPowerShell(script, "-Silencioso", null);
            if (c == 0) Log("Rede local liberada: outros computadores acessam pelo IP deste computador, porta 8080.");
            else if (c == 5) Log("Liberacao da rede cancelada. Quando quiser, use o atalho LIBERAR REDE LKI INDUSTRIAL.");
            else Log("A rede nao foi liberada (codigo " + c + "). Use o atalho LIBERAR REDE LKI INDUSTRIAL depois.");
        }

        static int RodarPowerShell(string script, string argumentos, Dictionary<string, string> env)
        {
            string ps = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell\\v1.0\\powershell.exe");
            if (!File.Exists(ps)) ps = "powershell.exe";
            ProcessStartInfo psi = new ProcessStartInfo(ps, "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\" " + argumentos);
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            // Sem PSModulePath herdado: se o instalador for aberto de um terminal
            // PowerShell 7, o Windows PowerShell 5.1 filho herdaria os modulos do 7
            // e perderia comandos basicos (Get-FileHash, NetSecurity). Removendo,
            // ele monta o caminho padrao dele. Achado no teste em Windows real.
            psi.EnvironmentVariables.Remove("PSModulePath");
            if (env != null) foreach (KeyValuePair<string, string> kv in env) psi.EnvironmentVariables[kv.Key] = kv.Value;
            Process p = new Process();
            p.StartInfo = psi;
            p.OutputDataReceived += delegate (object s, DataReceivedEventArgs e) { if (e.Data != null && e.Data.Trim().Length > 0) Log(e.Data.Trim()); };
            p.ErrorDataReceived += delegate (object s, DataReceivedEventArgs e) { if (e.Data != null && e.Data.Trim().Length > 0) Log("! " + e.Data.Trim()); };
            p.Start();
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            // NUNCA WaitForExit() sem prazo: ele espera tambem o fim da saida
            // redirecionada, e o servidor do sistema (iniciado pelo script e que
            // continua rodando) herda esse canal - a espera nunca terminava e o
            // instalador ficava parado em "Instalando..." (achado no teste em
            // Windows real, que ficou 6 h travado). Com prazo, a espera termina
            // quando o PowerShell sai, mesmo com o canal ainda aberto.
            while (!p.WaitForExit(500)) { }
            Thread.Sleep(300);   // ultimas linhas do registro
            return p.ExitCode;
        }

        // ------------------------------------------------------------------ utilidades
        static void Extrair(string recurso, string destino)
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(recurso))
            {
                if (s == null) throw new Exception("Recurso ausente no instalador: " + recurso);
                using (FileStream f = File.Create(destino)) { s.CopyTo(f); }
            }
        }

        static string Sha256(string arquivo)
        {
            using (SHA256 h = SHA256.Create())
            using (FileStream f = File.OpenRead(arquivo))
            {
                return BitConverter.ToString(h.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
            }
        }

        // Leitura minima de um campo de texto do versao.json (sem dependencias).
        static string LerCampoJson(string json, string campo)
        {
            string chave = "\"" + campo + "\"";
            int i = json.IndexOf(chave);
            if (i < 0) return "";
            i = json.IndexOf('"', json.IndexOf(':', i) + 1);
            int f = json.IndexOf('"', i + 1);
            return json.Substring(i + 1, f - i - 1);
        }

        static string VersaoEmbutida()
        {
            try
            {
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("versao.json"))
                using (StreamReader r = new StreamReader(s))
                {
                    string j = r.ReadToEnd();
                    string sha = LerCampoJson(j, "sha");
                    return LerCampoJson(j, "versao") + (sha.Length >= 7 ? " (" + sha.Substring(0, 7) + ")" : "");
                }
            }
            catch { return "?"; }
        }

        static void AbrirNavegador() { try { Process.Start(urlFinal); } catch { } }

        static void Log(string m)
        {
            if (logArquivo != null) { try { logArquivo.WriteLine(m); } catch { } }
            if (silencioso) { Console.WriteLine(m); return; }
            if (txtLog == null) return;
            txtLog.BeginInvoke((MethodInvoker)delegate { txtLog.AppendText(m + "\r\n"); });
        }

        static void Etapa(string m, int pct)
        {
            if (silencioso) { Console.WriteLine("[" + pct + "%] " + m); return; }
            if (lblEtapa == null) return;
            lblEtapa.BeginInvoke((MethodInvoker)delegate { lblEtapa.Text = m; barra.Value = Math.Max(0, Math.Min(100, pct)); });
        }
    }
}

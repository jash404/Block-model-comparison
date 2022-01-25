(self.webpackChunk_krassowski_jupyterlab_lsp=self.webpackChunk_krassowski_jupyterlab_lsp||[]).push([[47],{9258:(e,t,n)=>{"use strict";n.d(t,{Z:()=>i});var s=n(2609),r=n.n(s)()((function(e){return e[1]}));r.push([e.id,".lsp-completer-themes .lsp-licence {\n  display: inline;\n}\n\n.lsp-completer-themes ul {\n  list-style: none;\n  padding-left: 10px;\n}\n\n.lsp-completer-theme-icons {\n  margin-left: 10px;\n}\n\n.lsp-completer-icon-row {\n  width: 50%;\n  display: flex;\n  justify-content: space-between;\n}\n\n/* a workaround for scrollbars being always on in the completer documentation panel, see\n https://github.com/jupyter-lsp/jupyterlab-lsp/pull/322#issuecomment-682724175\n */\n.jp-Completer-docpanel {\n  overflow: auto;\n}\n\n.jp-Completer-match {\n  max-width: 400px;\n  overflow-x: hidden;\n  white-space: nowrap;\n  display: block;\n  text-overflow: ellipsis;\n}\n\n.jp-mod-active .jp-Completer-match {\n  max-width: 600px;\n  white-space: break-spaces;\n  height: auto;\n}\n\n.lsp-completer-placeholder:after {\n  content: 'Loading...';\n  color: #7f7f7f;\n}\n\n/* a workaround for code being larger font size than text in markdown-rendered panel */\n.jp-Completer-docpanel pre code {\n  font-size: 90%;\n}\n",""]);const i=r},6422:(e,t,n)=>{"use strict";n.r(t),n.d(t,{COMPLETION_THEME_MANAGER:()=>u,CompletionThemeManager:()=>p});var s=n(6062),r=n.n(s),i=n(9258);r()(i.Z,{insert:"head",singleton:!1}),i.Z.locals;var a=n(4835),o=n(242),c=n(8936),l=n(6271),h=n.n(l),m=n(5384);function d(e,t){let n=t.themes.map((n=>function(e,t,n,s){let r=[];for(let[e,s]of n(t))r.push(h().createElement("div",{className:"lsp-completer-icon-row"},h().createElement("div",null,e),h().createElement("div",{className:"jp-Completer-icon"},h().createElement(s.react,null))));return h().createElement("div",{className:"lsp-completer-themes "+m.wo+t.id},h().createElement("h4",null,t.name,s?e.__(" (current)"):""),h().createElement("ul",null,h().createElement("li",{key:"id"},"ID: ",h().createElement("code",null,t.id)),h().createElement("li",{key:"licence"},e.__("Licence: "),(i=t.icons.licence,h().createElement("div",{className:"lsp-licence"},h().createElement("a",{href:i.link,title:i.name},i.abbreviation)," ",i.licensor))),h().createElement("li",{key:"dark"},void 0===t.icons.dark?"":e.__("Includes dedicated dark mode icons set"))),h().createElement("div",{className:"lsp-completer-theme-icons"},r));var i}(e,n,t.get_set,n==t.current)));return h().createElement("div",null,n)}class p{constructor(e,t){this.themeManager=e,this.themes=new Map,this.icons_cache=new Map,this.icon_overrides=new Map,e.themeChanged.connect(this.update_icons_set,this),this.trans=t}is_theme_light(){const e=this.themeManager.theme;return!e||this.themeManager.isLight(e)}get_iconset(e){const t=e.icons,n=this.is_theme_light()||void 0===t.dark?t.light:t.dark,s=new Map;let r=this.current_theme.icons.options||{};const i=this.is_theme_light()?"light":"dark";for(let[t,a]of Object.entries(n)){let n,o="lsp:"+e.id+"-"+t.toLowerCase()+"-"+i;this.icons_cache.has(o)?n=this.icons_cache.get(o):(n=new c.LabIcon({name:o,svgstr:a}),this.icons_cache.set(o,n)),s.set(t,n.bindprops(r))}return s}update_icons_set(){null!==this.current_theme&&(this.current_icons=this.get_iconset(this.current_theme))}get_icon(e){return null===this.current_theme?null:(e&&(this.icon_overrides.has(e.toLowerCase())&&(e=this.icon_overrides.get(e.toLowerCase())),e=e.substring(0,1).toUpperCase()+e.substring(1).toLowerCase()),this.current_icons.has(e)?this.current_icons.get(e):e===m.OC?c.kernelIcon:null)}get current_theme_class(){return m.wo+this.current_theme_id}set_theme(e){this.current_theme_id&&document.body.classList.remove(this.current_theme_class),this.themes.has(e)||console.warn(`[LSP][Completer] Icons theme ${e} cannot be set yet (it may be loaded later).`),this.current_theme_id=e,document.body.classList.add(this.current_theme_class),this.update_icons_set()}get current_theme(){return this.themes.has(this.current_theme_id)?this.themes.get(this.current_theme_id):null}register_theme(e){this.themes.has(e.id)&&console.warn("Theme with name",e.id,"was already registered, overwriting."),this.themes.set(e.id,e),this.update_icons_set()}display_themes(){(0,a.showDialog)({title:this.trans.__("LSP Completer Themes"),body:d(this.trans,{themes:[...this.themes.values()],current:this.current_theme,get_set:this.get_iconset.bind(this)}),buttons:[a.Dialog.okButton({label:this.trans.__("OK")})]}).catch(console.warn)}set_icons_overrides(e){this.icon_overrides=new Map(Object.keys(e).map((t=>[t.toLowerCase(),e[t]])))}}const u={id:m.Uu,requires:[a.IThemeManager,a.ICommandPalette,o.ITranslator],activate:(e,t,n,s)=>{const r=s.load("jupyterlab_lsp");let i=new p(t,r);const a="lsp:completer-about-themes";return e.commands.addCommand(a,{label:r.__("Display the completer themes"),execute:()=>{i.display_themes()}}),n.addItem({category:"Language server protocol",command:a}),i},provides:m.kZ,autoStart:!0}}}]);
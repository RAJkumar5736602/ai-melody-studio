import re

PANEL = """
<div x-show="openId === song.id" x-cloak class="mt-1 bg-slate-900/80 border border-slate-800 rounded-xl p-4 text-xs text-slate-300 space-y-2">
  <div class="flex flex-wrap gap-4">
    <div><span class="text-slate-500">Genre:</span> <span x-text="song.genre || '-'"></span></div>
    <div><span class="text-slate-500">Mood:</span> <span x-text="song.mood || '-'"></span></div>
    <div><span class="text-slate-500">Created:</span> <span x-text="song.created_at ? new Date(song.created_at).toLocaleString() : '-'"></span></div>
  </div>
  <div><span class="text-slate-500">Prompt / Description:</span> <span x-text="song.prompt || '-'"></span></div>
  <div><span class="text-slate-500">Lyrics:</span>
    <pre class="whitespace-pre-wrap mt-1 text-slate-300 font-sans" x-text="song.lyrics || '(no lyrics - instrumental)'"></pre></div>
  <a x-show="song.status === 'completed' && song.audio_path" :href="'/api/mp3/' + song.id" :download="(song.title || 'song') + '.mp3'" @click.stop class="inline-block px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white font-semibold">Download song (MP3)</a>
  <a x-show="song.status === 'completed' && song.audio_path" :href="'/api/mp3/' + song.id" :download="(song.title || 'song') + '.mp3'" @click.stop class="ml-2 inline-block px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-white font-semibold">Share (downloads file)</a>
  <a x-show="song.status === 'completed' && song.audio_path" :href="song.audio_path" :download="(song.title || 'song') + '.wav'" @click.stop class="ml-2 inline-block px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-200 font-semibold">Download WAV (full quality)</a></div>
"""

DL = """<a x-show="song.status === 'completed' && song.audio_path" :href="'/api/mp3/' + song.id" :download="(song.title || 'song') + '.mp3'" @click.stop title="Download" class="p-2 text-slate-400 hover:text-indigo-400 transition"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3"></path></svg></a>
                                """

def patch(html):
    card = '<div class="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 hover:border-slate-700 transition flex items-center justify-between space-x-4">'
    if card in html:
        html = html.replace(card, '<div><div @click="openId = (openId === song.id ? null : song.id)" class="cursor-pointer bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 hover:border-slate-700 transition flex items-center justify-between space-x-4">', 1)
        html = re.sub(r'(deleteSong\(song\.id\)".*?</button>\s*</div>\s*)(</div>)(\s*</template>)',
                      lambda m: m.group(1) + '</div>' + PANEL + '</div>' + m.group(3), html, count=1, flags=re.S)
        for fn in ('toggleLike(song)', 'playSong(song)', 'deleteSong(song.id)'):
            html = html.replace('@click="%s"' % fn, '@click.stop="%s"' % fn)
        html = html.replace('<button @click.stop="deleteSong(song.id)"', DL + '<button @click.stop="deleteSong(song.id)"', 1)
        html = html.replace('currentSong: null,', 'currentSong: null,\n                openId: null,', 1)
    return html
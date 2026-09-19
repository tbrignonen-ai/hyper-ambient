import sounddevice as sd, numpy as np, wave, os, sys
D=os.path.dirname(os.path.abspath(__file__))
phrases=[l.strip() for l in open(os.path.join(D,'phrases.txt'),encoding='utf8') if l.strip()]
SR=16000
print("\n=== Dégustation OREILLE — 5 phrases ===\nParle naturellement, comme à MOTHER.\n")
for i,p in enumerate(phrases,1):
    print(f"\nPhrase {i}/5 :\n   « {p} »")
    input("   Entrée pour COMMENCER…")
    buf=[]
    st=sd.InputStream(samplerate=SR,channels=1,dtype='int16',callback=lambda d,f,t,s: buf.append(d.copy()))
    st.start(); input("   🔴 ENREGISTREMENT… Entrée pour ARRÊTER"); st.stop(); st.close()
    a=np.concatenate(buf) if buf else np.zeros((0,1),dtype='int16')
    f=os.path.join(D,'enregistrements',f'phrase{i}.wav')
    with wave.open(f,'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())
    print(f"   ✅ {len(a)/SR:.1f} s enregistrées")
print("\nC'est fini, merci ! Tu peux fermer cette fenêtre.")
input()

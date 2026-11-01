import com.android.apksig.ApkSigner;
import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.List;

/** java -cp apksig.jar:. Sign keystore.p12 password in.apk out.apk */
public class Sign {
    public static void main(String[] a) throws Exception {
        KeyStore ks = KeyStore.getInstance("PKCS12");
        FileInputStream in = new FileInputStream(a[0]);
        ks.load(in, a[1].toCharArray());
        in.close();
        String alias = ks.aliases().nextElement();
        PrivateKey key = (PrivateKey) ks.getKey(alias, a[1].toCharArray());
        List<X509Certificate> certs = new ArrayList<X509Certificate>();
        for (Certificate c : ks.getCertificateChain(alias)) certs.add((X509Certificate) c);
        List<ApkSigner.SignerConfig> cfg = new ArrayList<ApkSigner.SignerConfig>();
        cfg.add(new ApkSigner.SignerConfig.Builder("hl", key, certs).build());
        new ApkSigner.Builder(cfg).setInputApk(new File(a[2])).setOutputApk(new File(a[3]))
            .setMinSdkVersion(29).setV1SigningEnabled(false).setV2SigningEnabled(true).build().sign();
        System.out.println("signed " + a[3]);
    }
}
